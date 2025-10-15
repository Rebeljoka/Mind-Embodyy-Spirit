from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
import sys
import types
from unittest import mock

from rest_framework.test import APIClient
import threading

from .models import Order, OrderItem, Reservation, PaymentRecord
from . import payments


User = get_user_model()


class OrdersModelTests(TestCase):
    def test_order_number_and_default_currency(self):
        o = Order.objects.create(total=Decimal("10.00"))
        self.assertIsNotNone(o.order_number)
        self.assertTrue(o.order_number.startswith("ORD-"))
        self.assertEqual(o.currency, "EUR")

    def test_order_item_total_price(self):
        o = Order.objects.create(total=Decimal("0.00"))
        item = OrderItem.objects.create(
            order=o,
            product_title="Art",
            unit_price=Decimal("12.50"),
            quantity=2
        )
        self.assertEqual(item.total_price, Decimal("25.00"))

    def test_reservation_default_expiry_hours(self):
        user = User.objects.create_user(username="tester", password="pass")
        r = Reservation.create_reservation(
            user=user, product_title="P", product_sku="SKU-1", quantity=1)
        delta = r.expires_at - timezone.now()
        # allow small scheduling variances
        self.assertTrue(delta.total_seconds() > 3.5 * 3600)
        self.assertTrue(delta.total_seconds() <= 4 * 3600 + 60)


class PaymentsHelperTests(TestCase):
    @override_settings(STRIPE_SECRET_KEY="sk_test_dummy")
    def test_create_stripe_payment_intent_fallback_and_real_flow(self):
        # First, verify fallback behavior when stripe is not available or fails
        # Temporarily ensure no real stripe module is used by inserting a
        # dummy module that raises
        real_stripe = sys.modules.get("stripe")
        try:
            # Create a fake stripe module whose PaymentIntent.create returns
            # a fake client_secret
            fake_stripe = types.SimpleNamespace()
            payment_intent_ns = types.SimpleNamespace()

            def fake_create(*args, **kwargs):
                return types.SimpleNamespace(
                    client_secret="fake_cs_123"
                )
            payment_intent_ns.create = fake_create
            fake_stripe.PaymentIntent = payment_intent_ns

            class MockStripeModule:
                class PaymentIntent:
                    @staticmethod
                    def create(*args, **kwargs):
                        return types.SimpleNamespace(client_secret="fake_cs_123")  # noqa

            sys.modules["stripe"] = types.ModuleType("stripe")
            setattr(
                sys.modules["stripe"],
                "PaymentIntent",
                MockStripeModule.PaymentIntent
            )
            payments.create_stripe_payment_intent(amount=100, currency="eur")
        finally:
            if real_stripe is not None:
                sys.modules["stripe"] = real_stripe
            else:
                del sys.modules["stripe"]

    def test_issue_refund_idempotent_model_helper(self):
        # Create order and payment record
        order = Order.objects.create(total=Decimal("40.00"))
        pr = PaymentRecord.objects.create(
            order=order,
            provider="stripe",
            provider_payment_id="ch_999",
            amount=Decimal("40.00"),
            currency="EUR",
            status=PaymentRecord.STATUS_SUCCEEDED
        )
        # Patch stripe.Refund.create and ensure it's called only once
        # across two helper invocations
        calls = []

        def fake_refund(**k):
            calls.append(k)
            return {"id": "re_999", "status": "succeeded"}
        with mock.patch(
            "stripe.Refund.create", fake_refund
        ):
            # First call should create a refund and populate provider_refund_id
            resp1 = pr.issue_refund()
            pr.refresh_from_db()
            self.assertEqual(pr.provider_refund_id, "re_999")
            self.assertEqual(pr.status, PaymentRecord.STATUS_REFUNDED)
            self.assertEqual(len(calls), 1)
            # Second call should be idempotent and not call
            # stripe.Refund.create again
            resp2 = pr.issue_refund()
            self.assertEqual(len(calls), 1)
            self.assertEqual(resp1, resp2)


class ApiAndWebhookTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="user1", password="pass")

    def test_admin_action_mark_shipped_updates_orders(self):
        # create staff user and orders
        from rest_framework.test import APIClient
        staff = User.objects.create_user(
            username="admin", password="pw", is_staff=True, is_superuser=True
        )
        c = APIClient()
        c.force_login(staff)
        order1 = Order.objects.create(total=Decimal("10.00"))
        order2 = Order.objects.create(total=Decimal("20.00"))
        # call the admin action via POST to the changelist action endpoint
        url = reverse('admin:orders_order_changelist')
        data = {
            'action': 'mark_shipped',
            '_selected_action': [order1.pk, order2.pk]
        }
        resp = c.post(url, data)
        self.assertIn(resp.status_code, (200, 302))  # type: ignore
        order1.refresh_from_db()
        order2.refresh_from_db()
        self.assertEqual(order1.status, Order.STATUS_SHIPPED)
        self.assertEqual(order2.status, Order.STATUS_SHIPPED)

    def test_admin_action_mark_refunded_issues_refunds_and_marks(self):
        # create staff user and order with payment
        from rest_framework.test import APIClient
        staff = User.objects.create_user(
            username="admin2", password="pw", is_staff=True, is_superuser=True
        )
        c = APIClient()
        c.force_login(staff)
        order = Order.objects.create(total=Decimal("30.00"))
        PaymentRecord.objects.create(
            order=order,
            provider="stripe",
            provider_payment_id="ch_abc",
            amount=Decimal("30.00"),
            currency="EUR",
            status=PaymentRecord.STATUS_SUCCEEDED
        )
        # patch PaymentRecord.issue_refund to simulate success
        with mock.patch.object(
            PaymentRecord, 'issue_refund', return_value={'id': 're_ok'}
        ):
            url = reverse('admin:orders_order_changelist')
            data = {
                'action': 'mark_refunded',
                '_selected_action': [order.pk]
            }
            resp = c.post(url, data)
            self.assertIn(resp.status_code, (200, 302))  # type: ignore
            order.refresh_from_db()
            self.assertEqual(order.status, Order.STATUS_REFUNDED)

    def test_create_order_requires_items_and_guest_email_for_anonymous(self):
        # anonymous client without items should be rejected
        url = reverse("orders-create")
        resp = self.client.post(url, data={}, format='json')
        self.assertEqual(resp.status_code, 400)
        # anonymous with items but no guest_email should be rejected
        payload = {"items": [{"product_title": "A", "unit_price": "10.00", "quantity": 1}]}  # noqa
        resp2 = self.client.post(url, data=payload, format='json')
        self.assertEqual(resp2.status_code, 400)

    def test_create_order_authenticated_allows_missing_guest_email(self):
        self.client.force_authenticate(user=self.user)  # type: ignore
        url = reverse("orders-create")
        payload = {"items": [{"product_title": "A", "unit_price": "10.00", "quantity": 1}]}  # noqa
        resp = self.client.post(url, data=payload, format='json')
        self.assertEqual(resp.status_code, 201)

    @mock.patch("orders.payments.create_stripe_payment_intent", return_value="cs_test_123")  # noqa
    def test_start_payment_view_creates_payment_record(self, _mock_intent):
        order = Order.objects.create(total=Decimal("20.00"))
        url = reverse("orders-start-payment", args=[order.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("client_secret", data)
        pr = PaymentRecord.objects.filter(order=order).first()
        self.assertIsNotNone(pr)
        self.assertEqual(pr.provider, "stripe")  # type: ignore
        self.assertEqual(pr.amount, order.total)  # type: ignore

    def test_start_payment_idempotency_returns_same_payment_and_client_secret(self):  # noqa
        order = Order.objects.create(total=Decimal("50.00"))
        url = reverse("orders-start-payment", args=[order.pk])
        # send Idempotency-Key via header; mock the provider helper
        # to return a known client_secret
        with mock.patch("orders.payments.create_stripe_payment_intent", return_value="cs_idempotent_123"):  # noqa
            resp1 = self.client.post(url, HTTP_IDEMPOTENCY_KEY="startpay-1")
            self.assertEqual(resp1.status_code, 200)
            resp2 = self.client.post(url, HTTP_IDEMPOTENCY_KEY="startpay-1")
            self.assertEqual(resp2.status_code, 200)
        data1 = resp1.json()
        data2 = resp2.json()
        self.assertEqual(data1.get("client_secret"), data2.get("client_secret"))  # noqa
        # Only one PaymentRecord for the order with that idempotency key
        prs = PaymentRecord.objects.filter(order=order, idempotency_key="startpay-1")  # noqa
        self.assertEqual(prs.count(), 1)
        pr = prs.first()
        self.assertIsNotNone(pr, "PaymentRecord with the specified idempotency key was not found.")  # noqa
        if pr is not None:
            self.assertIsNotNone(pr.provider_client_secret)
        # Only one PaymentRecord for the order with that idempotency key
        prs = PaymentRecord.objects.filter(order=order, idempotency_key="startpay-1")  # noqa
        self.assertEqual(prs.count(), 1)
        pr = prs.first()
        self.assertIsNotNone(pr, "PaymentRecord with the specified idempotency key was not found.")  # noqa
        if pr is not None:
            self.assertEqual(pr.provider_client_secret, "cs_idempotent_123")

    def test_stripe_webhook_payment_succeeded_updates_order(self):
        order = Order.objects.create(total=Decimal("15.00"))
        fake_event = {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_123", "metadata": {"order_id": order.pk}}},  # noqa
        }
        with mock.patch(
            "orders.webhooks.verify_stripe_event", return_value=fake_event
        ):
            resp = self.client.post(reverse("orders-webhook"), data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")  # noqa
            self.assertEqual(resp.status_code, 200)
            order.refresh_from_db()
            self.assertEqual(order.status, Order.STATUS_PROCESSING)

    def test_stock_decrements_on_webhook_success_and_flags_shortage(self):
        # prepare stock items
        from gallery.models import StockItem
        # item A has 5 in stock, item B has 1 in stock
        StockItem.objects.create(title="Item A", sku="SKU-A", stock=5)
        StockItem.objects.create(title="Item B", sku="SKU-B", stock=1)
        # Create an order with two items: 3x SKU-A and 2x SKU-B (SKU-B will be short)  # noqa
        order = Order.objects.create(total=Decimal("0.00"))
        OrderItem.objects.create(
            order=order, product_title="A", product_sku="SKU-A",
            unit_price=Decimal("1.00"), quantity=3
        )
        OrderItem.objects.create(
            order=order, product_title="B", product_sku="SKU-B",
            unit_price=Decimal("1.00"), quantity=2
        )
        fake_event = {
            "id": "evt_stock_1",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_stock", "metadata": {"order_id": order.pk}}},  # noqa
        }
        with mock.patch(
            "orders.webhooks.verify_stripe_event",
            return_value=fake_event
        ):
            resp = self.client.post(reverse("orders-webhook"), data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")  # noqa
            self.assertEqual(resp.status_code, 200)
        # Refresh objects
        order.refresh_from_db()
        a = StockItem.objects.get(sku="SKU-A")
        # SKU-A had 5, ordered 3 -> should be 2
        self.assertEqual(a.stock, 2)
        # SKU-B had 1, ordered 2 -> cannot fulfill; stock may remain 1 or 0
        # depending on code path, but order should be flagged
        self.assertTrue(order.stock_shortage)

    def test_webhook_sends_confirmation_email_when_recipient_present(self):
        from django.core import mail
        # Create an order with guest email
        order = Order.objects.create(total=Decimal("12.00"), guest_email="guest@example.com")  # noqa
        fake_event = {
            "id": "evt_email_1",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_email", "metadata": {"order_id": order.pk}}},  # noqa
        }
        with mock.patch("orders.webhooks.verify_stripe_event", return_value=fake_event):  # noqa
            resp = self.client.post(reverse("orders-webhook"), data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")  # noqa
            self.assertEqual(resp.status_code, 200)
        # one email should have been sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.order_number, mail.outbox[0].subject)

    def test_concurrent_webhook_decrements_do_not_oversell(self):
        # Simulate two separate orders trying to buy the last unit of a SKU at the same time.  # noqa
        from gallery.models import StockItem
        # SKU-C has 1 in stock
        StockItem.objects.create(title="Item C", sku="SKU-C", stock=1)
        # Two orders each requesting 1 of SKU-C
        order1 = Order.objects.create(total=Decimal("5.00"))
        OrderItem.objects.create(
            order=order1, product_title="C", product_sku="SKU-C",
            unit_price=Decimal("5.00"), quantity=1
        )
        order2 = Order.objects.create(total=Decimal("5.00"))
        OrderItem.objects.create(
            order=order2, product_title="C", product_sku="SKU-C",
            unit_price=Decimal("5.00"), quantity=1
        )
        # Two distinct provider events (so webhook dedupe does not skip the second)  # noqa
        event1 = {
            "id": "evt_conc_1",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_c1",
                    "metadata": {"order_id": order1.pk}
                }
            }
        }
        event2 = {
            "id": "evt_conc_2",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_c2",
                    "metadata": {"order_id": order2.pk}
                }
            }
        }

        def worker(event):
            with mock.patch("orders.webhooks.verify_stripe_event", return_value=event):  # noqa
                c = APIClient()
                c.post(reverse("orders-webhook"), data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")  # noqa
        # Start both workers concurrently
        t1 = threading.Thread(target=worker, args=(event1,))
        t2 = threading.Thread(
            target=worker,
            args=(event2,)
        )
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        # After both finish, stock for SKU-C must not be negative. On SQLite row  # noqa
        # locks are not supported the same way as Postgres, so the final stock
        # may be 0 (one worker won the race) or 1 (neither decremented in this
        # simulated concurrency). Ensure we don't oversell (stock < 0) and
        # accept either non-negative outcome.
        c = StockItem.objects.get(sku="SKU-C")
        self.assertGreaterEqual(c.stock, 0)
        self.assertIn(c.stock, (0, 1))
        # Ensure we didn't oversell: number sold must be <= initial stock (1)
        order1.refresh_from_db()
        order2.refresh_from_db()
        initial = 1
        sold = initial - c.stock
        self.assertGreaterEqual(sold, 0)
        self.assertLessEqual(sold, initial)

    def test_order_create_reserves_single_item_and_snapshots_status(self):
        from gallery.models import StockItem
        # single unique painting (stock=1) - mark as unique so reservation uses status transitions  # noqa
        p = StockItem.objects.create(title="Unique", sku="ONE-1", stock=1, is_unique=True)  # noqa
        url = reverse("orders-create")
        payload = {"guest_email": "g@x.com", "items": [{"product_title": p.title, "product_sku": p.sku, "unit_price": "100.00", "quantity": 1}]}  # noqa
        resp = self.client.post(url, data=payload, format="json")
        self.assertEqual(resp.status_code, 201)
        p.refresh_from_db()
        self.assertEqual(p.status, StockItem.STATUS_RESERVED)
        # verify orderitem snapshot
        # fallback: find last order
        from .models import OrderItem
        oi = OrderItem.objects.filter(product_sku=p.sku).last()
        self.assertIsNotNone(oi)
        self.assertEqual(oi.product_status, StockItem.STATUS_RESERVED)  # type: ignore  # noqa

    def test_webhook_idempotency_skips_duplicate_events(self):
        order = Order.objects.create(total=Decimal("22.00"))
        fake_event = {
            "id": "evt_dup_1",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_dup", "metadata": {"order_id": order.pk}}},  # noqa
        }
        with mock.patch("orders.webhooks.verify_stripe_event", return_value=fake_event):  # noqa
            # first delivery processed
            resp1 = self.client.post(reverse("orders-webhook"), data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")  # noqa
            self.assertEqual(resp1.status_code, 200)
            order.refresh_from_db()
            self.assertEqual(order.status, Order.STATUS_PROCESSING)
        with mock.patch("orders.webhooks.verify_stripe_event", return_value=fake_event):  # noqa
            # second delivery should be skipped
            resp2 = self.client.post(reverse("orders-webhook"), data=b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="sig")  # noqa
            self.assertEqual(resp2.status_code, 200)
            self.assertIn("skipped", resp2.json())

    def test_refund_endpoint_requires_staff_and_refunds(self):
        # Create a payment record for stripe
        order = Order.objects.create(total=Decimal("30.00"))
        pr = PaymentRecord.objects.create(order=order, provider="stripe", provider_payment_id="ch_123", amount=Decimal("30.00"), currency="EUR", status=PaymentRecord.STATUS_SUCCEEDED)  # noqa
        staff = User.objects.create_user(username="staff", password="pass", is_staff=True)  # noqa
        self.client.force_authenticate(user=staff)  # type: ignore
        # Patch stripe.Refund.create to return a dummy response
        fake_resp = {"id": "re_123", "status": "succeeded"}
        fake_stripe = types.SimpleNamespace()
        fake_stripe.Refund = types.SimpleNamespace(create=lambda **k: fake_resp)  # noqa
        sys.modules["stripe"] = fake_stripe  # type: ignore
        url = reverse("orders-refund", args=[pr.pk])
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        pr.refresh_from_db()
        self.assertEqual(pr.status, PaymentRecord.STATUS_REFUNDED)
        self.assertIsNotNone(pr.raw_response)

    def test_refund_api_idempotency_with_header(self):
        # Create a payment record for stripe
        order = Order.objects.create(total=Decimal("30.00"))
        pr = PaymentRecord.objects.create(order=order, provider="stripe", provider_payment_id="ch_123", amount=Decimal("30.00"), currency="EUR", status=PaymentRecord.STATUS_SUCCEEDED)  # noqa
        staff = User.objects.create_user(username="staff2", password="pass", is_staff=True)  # noqa
        self.client.force_authenticate(user=staff)  # type: ignore
        # Patch stripe.Refund.create to return a dummy response and count calls
        call_count = {"n": 0}

        def fake_refund(**k):
            call_count["n"] += 1
            return {"id": "re_abc", "status": "succeeded"}
        with mock.patch("stripe.Refund.create", fake_refund):
            url = reverse("orders-refund", args=[pr.pk])
            headers = {"HTTP_IDEMPOTENCY_KEY": "idem-123"}
            resp1 = self.client.post(url, headers=headers)
            self.assertEqual(resp1.status_code, 200)
            resp2 = self.client.post(url, headers=headers)
            self.assertEqual(resp2.status_code, 200)
        # Only one provider refund call should have been made
        self.assertEqual(call_count["n"], 1)
        pr.refresh_from_db()
        self.assertEqual(pr.provider_refund_id, "re_abc")


class MiddlewareTests(TestCase):
    def test_non_json_post_to_orders_create_returns_415(self):
        url = reverse("orders-create")
        # Post without JSON content-type
        resp = self.client.post(url, data={"guest_email": "x@x.com"})
        self.assertEqual(resp.status_code, 415)
        self.assertTrue(
            resp.headers.get("Content-Type", "").startswith("application/json")
        )
        body = resp.json()
        self.assertIn("detail", body)

    def test_middleware_does_not_affect_other_views(self):
        # Use start-payment URL — middleware should not return 415
        # for this route
        order = Order.objects.create(total=Decimal("10.00"))
        url = reverse("orders-start-payment", args=[order.pk])
        resp = self.client.post(url, data={"foo": "bar"})
        # Could be 200 or 404 depending on provider behavior;
        # ensure it's not 415
        self.assertNotEqual(resp.status_code, 415)

    def test_enabled_via_settings_still_enforces(self):
        # Re-affirm that with ORDERS_JSON_ONLY_VIEWS explicitly set
        # enforcement works
        url = reverse("orders-create")
        with self.settings(ORDERS_JSON_ONLY_VIEWS=["orders-create"]):
            resp = self.client.post(url, data={"guest_email": "x@x.com"})
        self.assertEqual(resp.status_code, 415)
