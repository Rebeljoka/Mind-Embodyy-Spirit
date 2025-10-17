from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import EventForm
from .models import Event


@override_settings(
	SECURE_SSL_REDIRECT=False,
	SESSION_COOKIE_SECURE=False,
	CSRF_COOKIE_SECURE=False,
)
class EventModelTests(TestCase):
	def test_str_representation(self):
		today = timezone.localdate()
		e = Event.objects.create(
			event_name="Gallery Opening",
			location="Main Hall",
			event_date=today,
		)
		self.assertEqual(str(e), f"Gallery Opening on {today}")

	def test_event_date_cannot_be_in_past_by_validator(self):
		yesterday = timezone.localdate() - timedelta(days=1)
		event = Event(
			event_name="Past Event",
			location="Somewhere",
			event_date=yesterday,
		)
		# Model field validators run on full_clean()
		with self.assertRaises(ValidationError):
			event.full_clean()


@override_settings(
	SECURE_SSL_REDIRECT=False,
	SESSION_COOKIE_SECURE=False,
	CSRF_COOKIE_SECURE=False,
)
class EventFormTests(TestCase):
	def test_form_valid_with_today_date(self):
		today = timezone.localdate()
		form = EventForm(
			data={
				"event_name": "Workshop",
				"location": "Studio",
				"event_date": today,
			}
		)
		self.assertTrue(form.is_valid())

	def test_form_invalid_with_past_date(self):
		past = timezone.localdate() - timedelta(days=1)
		form = EventForm(
			data={
				"event_name": "Past",
				"location": "There",
				"event_date": past,
			}
		)
		self.assertFalse(form.is_valid())
		self.assertIn("event_date", form.errors)

	def test_form_invalid_with_non_image_poster(self):
		today = timezone.localdate()
		fake_txt = SimpleUploadedFile(
			"readme.txt",
			b"not an image",
			content_type="text/plain",
		)
		form = EventForm(
			data={
				"event_name": "Talk",
				"location": "Auditorium",
				"event_date": today,
			},
			files={"poster": fake_txt},
		)
		self.assertFalse(form.is_valid())
		self.assertIn("poster", form.errors)

	def test_form_invalid_when_poster_exceeds_size(self):
		today = timezone.localdate()
		# Create a file slightly over 5MB
		big_content = b"0" * (5 * 1024 * 1024 + 1)
		big_file = SimpleUploadedFile(
			"big.jpg",
			big_content,
			content_type="image/jpeg",
		)
		form = EventForm(
			data={
				"event_name": "Expo",
				"location": "Hall",
				"event_date": today,
			},
			files={"poster": big_file},
		)
		self.assertFalse(form.is_valid())
		self.assertIn("poster", form.errors)


@override_settings(
	SECURE_SSL_REDIRECT=False,
	SESSION_COOKIE_SECURE=False,
	CSRF_COOKIE_SECURE=False,
)
class EventListViewTests(TestCase):
	def setUp(self):
		self.url = reverse("events:events")

	def test_list_shows_only_today_and_future_sorted(self):
		today = timezone.localdate()
		past = today - timedelta(days=1)
		future1 = today + timedelta(days=1)
		future2 = today + timedelta(days=2)

		Event.objects.create(event_name="Past", location="A", event_date=past)
		e_today = Event.objects.create(event_name="Today", location="B", event_date=today)
		e_future1 = Event.objects.create(event_name="Soon", location="C", event_date=future1)
		e_future2 = Event.objects.create(event_name="Later", location="D", event_date=future2)

		resp = self.client.get(self.url)
		self.assertEqual(resp.status_code, 200)

		events = list(resp.context["events"])  # page_obj is iterable
		self.assertEqual([e.event_name for e in events], [
			e_today.event_name,
			e_future1.event_name,
			e_future2.event_name,
		])

	def test_pagination_two_pages(self):
		today = timezone.localdate()
		# Create 4 future/today events (paginator is 3 per page)
		for i in range(4):
			Event.objects.create(
				event_name=f"E{i}",
				location="L",
				event_date=today + timedelta(days=i),
			)

		resp_page1 = self.client.get(self.url)
		self.assertEqual(resp_page1.status_code, 200)
		page_obj1 = resp_page1.context["page_obj"]
		self.assertEqual(page_obj1.paginator.num_pages, 2)
		self.assertEqual(len(list(page_obj1.object_list)), 3)

		resp_page2 = self.client.get(self.url + "?page=2")
		page_obj2 = resp_page2.context["page_obj"]
		self.assertEqual(len(list(page_obj2.object_list)), 1)


@override_settings(
	SECURE_SSL_REDIRECT=False,
	SESSION_COOKIE_SECURE=False,
	CSRF_COOKIE_SECURE=False,
)
class EventMutationViewTests(TestCase):
	def setUp(self):
		User = get_user_model()
		self.superuser = User.objects.create_superuser(
			username="admin",
			email="admin@example.com",
			password="pass1234",
		)
		self.user = User.objects.create_user(
			username="user",
			email="user@example.com",
			password="pass1234",
		)

		self.list_url = reverse("events:events")
		self.new_url = reverse("events:event_new")

		today = timezone.localdate()
		self.event = Event.objects.create(
			event_name="Edit Me",
			location="Room 1",
			event_date=today + timedelta(days=1),
		)
		self.edit_url = reverse("events:event_edit", args=[self.event.pk])
		self.delete_url = reverse("events:event_delete", args=[self.event.pk])

	def test_new_event_requires_superuser(self):
		self.client.login(username="user", password="pass1234")
		today = timezone.localdate()
		resp = self.client.post(
			self.new_url,
			data={
				"event_name": "Unauthorized",
				"location": "X",
				"event_date": today,
			},
			follow=True,
		)
		self.assertRedirects(resp, self.list_url)
		msgs = [m.message for m in get_messages(resp.wsgi_request)]
		self.assertTrue(any("do not have permission" in m for m in msgs))
		self.assertFalse(Event.objects.filter(event_name="Unauthorized").exists())

	def test_superuser_can_create_event(self):
		self.client.login(username="admin", password="pass1234")
		today = timezone.localdate()
		resp = self.client.post(
			self.new_url,
			data={
				"event_name": "Created",
				"location": "Y",
				"event_date": today + timedelta(days=3),
			},
			follow=True,
		)
		self.assertRedirects(resp, self.list_url)
		self.assertTrue(Event.objects.filter(event_name="Created").exists())
		msgs = [m.message for m in get_messages(resp.wsgi_request)]
		self.assertTrue(any("successfully added" in m for m in msgs))

	def test_edit_requires_superuser(self):
		self.client.login(username="user", password="pass1234")
		resp = self.client.post(
			self.edit_url,
			data={
				"event_name": "Hacked",
				"location": self.event.location,
				"event_date": self.event.event_date,
			},
			follow=True,
		)
		self.assertRedirects(resp, self.list_url)
		self.event.refresh_from_db()
		self.assertNotEqual(self.event.event_name, "Hacked")

	def test_superuser_can_edit_event(self):
		self.client.login(username="admin", password="pass1234")
		resp = self.client.post(
			self.edit_url,
			data={
				"event_name": "Updated",
				"location": "Room 9",
				"event_date": (timezone.localdate() + timedelta(days=5)).isoformat(),
			},
			follow=True,
		)
		self.assertRedirects(resp, self.list_url)
		self.event.refresh_from_db()
		self.assertEqual(self.event.event_name, "Updated")
		self.assertEqual(self.event.location, "Room 9")

	def test_edit_with_invalid_data_shows_error_and_does_not_change(self):
		self.client.login(username="admin", password="pass1234")
		past = timezone.localdate() - timedelta(days=1)
		old_name = self.event.event_name
		resp = self.client.post(
			self.edit_url,
			data={
				"event_name": "Bad",
				"location": "Room 1",
				"event_date": past.isoformat(),
			},
			follow=True,
		)
		self.assertRedirects(resp, self.list_url)
		self.event.refresh_from_db()
		self.assertEqual(self.event.event_name, old_name)
		msgs = [m.message for m in get_messages(resp.wsgi_request)]
		self.assertTrue(any("Error updating event" in m for m in msgs))

	def test_delete_requires_post_and_superuser(self):
		# Non-POST rejected
		self.client.login(username="admin", password="pass1234")
		resp_get = self.client.get(self.delete_url, follow=True)
		self.assertRedirects(resp_get, self.list_url)
		self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

		# Non-superuser POST rejected
		self.client.logout()
		self.client.login(username="user", password="pass1234")
		resp_post_user = self.client.post(self.delete_url, follow=True)
		self.assertRedirects(resp_post_user, self.list_url)
		self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

	def test_superuser_can_delete_with_post(self):
		self.client.login(username="admin", password="pass1234")
		resp = self.client.post(self.delete_url, follow=True)
		self.assertRedirects(resp, self.list_url)
		self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

