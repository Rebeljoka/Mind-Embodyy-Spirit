from django.test import TestCase, Client
from django.urls import reverse, NoReverseMatch
from django.core import mail
from django.test.utils import override_settings
from django.conf import settings

from newsletter.models import Subscriber, SubscriptionEvent


TEST_STORAGES = {**getattr(settings, "STORAGES", {})}
TEST_STORAGES["staticfiles"] = {
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
}

@override_settings(
    STORAGES=TEST_STORAGES,
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class NewsletterFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.email = "user@example.com"

    def test_subscribe_sends_email_and_confirms(self):
        # 1) APPI subscribe endpoint
        resp = self.client.post(
            reverse("newsletter:subscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        sub = Subscriber.objects.get(email=self.email)
        self.assertEqual(sub.status, Subscriber.PENDING)
        self.assertTrue(sub.confirm_token)

        # 2) mail sent include token/link
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        body = msg.body
        if getattr(msg, "alternatives", None):
            #  if HTML version exists, we also check it
            body += msg.alternatives[0][0]
        self.assertIn(sub.confirm_token, body)

        # 3) Confirmation by token redirects to confirmed and marks as SUBSCRIBED
        confirm_url = reverse("newsletter:confirm") + f"?token={sub.confirm_token}"
        resp2 = self.client.get(confirm_url, follow=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertIn(reverse("newsletter:confirmed"), resp2["Location"])

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscriber.SUBSCRIBED)
        self.assertIsNotNone(sub.consent_at)

        # 4) Auditory events created
        self.assertTrue(
            SubscriptionEvent.objects.filter(subscriber=sub, event_type="requested").exists()
        )
        self.assertTrue(
            SubscriptionEvent.objects.filter(subscriber=sub, event_type="confirmed").exists()
        )

    def test_confirm_invalid_token_redirects_to_invalid(self):
        resp = self.client.get(reverse("newsletter:confirm") + "?token=invalid", follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("newsletter:invalid"), resp["Location"])

    def test_unsubscribe_api_and_done_page(self):
        # Create a subscribed user
        sub = Subscriber.objects.create(email=self.email, status=Subscriber.SUBSCRIBED)

        # 1) Desuscripción vía API
        resp = self.client.post(
            reverse("newsletter:unsubscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscriber.UNSUBSCRIBED)
        self.assertIsNotNone(sub.unsubscribed_at)
        self.assertTrue(
            SubscriptionEvent.objects.filter(subscriber=sub, event_type="unsubscribed").exists()
        )

        # 2) confirmation page unsubscribe
        done_resp = self.client.get(reverse("newsletter:unsubscribe_done"))
        self.assertEqual(done_resp.status_code, 200)

    def test_subscribe_page_served_with_csrf(self):
        resp = self.client.get(reverse("newsletter:subscribe_page"))
        self.assertEqual(resp.status_code, 200)
        # TemplateView ensures CSRF cookie
        self.assertIn("csrftoken", resp.cookies)

    def test_unsubscribe_page_if_present(self):
        # This is a optional page; if not registered, we skip the test
        try:
            url = reverse("newsletter:unsubscribe_page")
        except NoReverseMatch:
            self.skipTest("unsubscribe_page not configured")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("csrftoken", resp.cookies)

    def test_resubscribe_from_unsubscribed_sets_pending(self):
        # If a UNSUBSCRIBED user resubscribes, it should go to PENDING
        sub = Subscriber.objects.create(email=self.email, status=Subscriber.UNSUBSCRIBED)
        resp = self.client.post(
            reverse("newsletter:subscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscriber.PENDING)

    def test_00_static_backend(self):
        backend = settings.STORAGES["staticfiles"]["BACKEND"]
        self.assertEqual(
            backend,
            "django.contrib.staticfiles.storage.StaticFilesStorage"
        )

    def test_email_template_contains_confirm_link_and_cta(self):
        # Subscribing should send an email containing the token and a clear CTA
        resp = self.client.post(
            reverse("newsletter:subscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        body = msg.body
        html = ""
        if getattr(msg, "alternatives", None):
            html = msg.alternatives[0][0]
            body += html

        sub = Subscriber.objects.get(email=self.email)
        # Token must be present somewhere in the email (plain or HTML)
        self.assertIn(sub.confirm_token, body)
        # Adjust the CTA text to match your template copy
        self.assertTrue(("Confirm subscription" in body) or ("Confirm your subscription" in body))

    def test_resubscribe_when_pending_resends_email_and_keeps_pending(self):
        # First subscription -> PENDING + 1 email
        self.client.post(
            reverse("newsletter:subscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 1)
        sub = Subscriber.objects.get(email=self.email)
        self.assertEqual(sub.status, Subscriber.PENDING)
        first_token = sub.confirm_token

        # Second attempt while still PENDING -> send another email (token may or may not change)
        self.client.post(
            reverse("newsletter:subscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(len(mail.outbox), 2)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscriber.PENDING)
        # If you regenerate the token on every request, uncomment:
        # self.assertNotEqual(sub.confirm_token, first_token)

    def test_unsubscribe_is_idempotent(self):
        Subscriber.objects.create(email=self.email, status=Subscriber.SUBSCRIBED)

        # First unsubscribe
        r1 = self.client.post(
            reverse("newsletter:unsubscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertIn(r1.status_code, (200, 204))

        # Second unsubscribe (should not break state and should be safe)
        r2 = self.client.post(
            reverse("newsletter:unsubscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertIn(r2.status_code, (200, 204))

        sub = Subscriber.objects.get(email=self.email)
        self.assertEqual(sub.status, Subscriber.UNSUBSCRIBED)

    def test_confirm_without_token_redirects_to_invalid(self):
        # Hitting confirm without ?token should redirect to the invalid page
        resp = self.client.get(reverse("newsletter:confirm"), follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("newsletter:invalid"), resp["Location"])


    def test_unsubscribe_page_flow_redirects_to_done(self):
        # If the optional unsubscribe page is not wired, skip the test
        try:
            page_url = reverse("newsletter:unsubscribe_page")
        except NoReverseMatch:
            self.skipTest("unsubscribe_page not configured")

        # Render page (ensures CSRF cookie is set in your TemplateView)
        page_resp = self.client.get(page_url)
        self.assertEqual(page_resp.status_code, 200)

        # Create a subscribed user, then post to the API endpoint
        Subscriber.objects.create(email=self.email, status=Subscriber.SUBSCRIBED)
        api_resp = self.client.post(
            reverse("newsletter:unsubscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertIn(api_resp.status_code, (200, 204))

        # Finally, the done page should render successfully
        done_resp = self.client.get(reverse("newsletter:unsubscribe_done"))
        self.assertEqual(done_resp.status_code, 200)

    def test_email_defaults_to_english_without_locale(self):
        resp = self.client.post(
            reverse("newsletter:subscribe"),
            data={"email": self.email},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

        msg = mail.outbox[0]
        plain = msg.body
        html = msg.alternatives[0][0] if getattr(msg, "alternatives", None) else ""

        sub = Subscriber.objects.get(email=self.email)
        self.assertTrue(sub.confirm_token in plain or sub.confirm_token in html)

        en_subject_ok = ("Confirm your subscription" in msg.subject) or ("Confirm subscription" in msg.subject)
        en_body_ok = ("Confirm your subscription" in plain) or ("Confirm subscription" in plain) or ("Confirm" in html)
        self.assertTrue(en_subject_ok or en_body_ok)
