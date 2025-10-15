from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

class Address(models.Model):
	SHIPPING = "shipping"
	BILLING = "billing"
	ADDRESS_TYPE_CHOICES = [
		(SHIPPING, "Shipping"),
		(BILLING, "Billing"),
	]

	order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="addresses")
	address_type = models.CharField(max_length=16, choices=ADDRESS_TYPE_CHOICES)
	full_name = models.CharField(max_length=255)
	line1 = models.CharField(max_length=255)
	line2 = models.CharField(max_length=255, blank=True)
	city = models.CharField(max_length=128)
	region = models.CharField(max_length=128, blank=True)
	postal_code = models.CharField(max_length=32)
	country = models.CharField(max_length=64)
	phone = models.CharField(max_length=32, blank=True)

	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.address_type.title()} address for order {self.order_id}"

class Order(models.Model):
	STATUS_PAID = "paid"
	STATUS_PROCESSING = "processing"
	STATUS_SHIPPED = "shipped"
	STATUS_CANCELLED = "cancelled"
	STATUS_REFUNDED = "refunded"

	STATUS_CHOICES = [
		(STATUS_PAID, "Paid"),
		(STATUS_PROCESSING, "Processing"),
		(STATUS_SHIPPED, "Shipped"),
		(STATUS_CANCELLED, "Cancelled"),
		(STATUS_REFUNDED, "Refunded"),
	]

	order_number = models.CharField(max_length=32, unique=True, blank=True)
	user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
	guest_email = models.EmailField(null=True, blank=True)
	status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_PAID)
	total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	# Store currency per-order. Default to EUR; multi-currency supported.
	currency = models.CharField(max_length=8, default="EUR")
	# Flag indicating that stock was insufficient when processing payment
	stock_shortage = models.BooleanField(default=False)

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return self.order_number or f"Order {self.pk}"

	def save(self, *args, **kwargs):
		# On first save generate a human friendly order number using the PK
		is_new = self.pk is None
		super().save(*args, **kwargs)
		if not self.order_number:
			self.order_number = f"ORD-{self.pk:06d}"
			# save again but avoid recursion
			Order.objects.filter(pk=self.pk).update(order_number=self.order_number)

	@property
	def items(self):
		return self.order_items.all()

class OrderItem(models.Model):
	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_items")

	# Optional link to a product model if one exists in another app
	content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
	object_id = models.PositiveIntegerField(null=True, blank=True)
	product_object = GenericForeignKey("content_type", "object_id")

	# Snapshot fields so orders do not break if product later changes or is deleted
	product_title = models.CharField(max_length=255)
	product_sku = models.CharField(max_length=64, blank=True)
	# Snapshot of product status at the time of ordering (available/reserved/sold/archived)
	product_status = models.CharField(max_length=16, blank=True, null=True)
	unit_price = models.DecimalField(max_digits=10, decimal_places=2)
	quantity = models.PositiveIntegerField(default=1)

	def __str__(self):
		return f"{self.product_title} x{self.quantity} ({self.order.order_number})"

	@property
	def total_price(self):
		return self.unit_price * self.quantity

class PaymentRecord(models.Model):
	STATUS_PENDING = "pending"
	STATUS_SUCCEEDED = "succeeded"
	STATUS_FAILED = "failed"
	STATUS_REFUNDED = "refunded"

	STATUS_CHOICES = [
		(STATUS_PENDING, "Pending"),
		(STATUS_SUCCEEDED, "Succeeded"),
		(STATUS_FAILED, "Failed"),
		(STATUS_REFUNDED, "Refunded"),
	]

	order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
	provider = models.CharField(max_length=64)  # e.g., stripe, paypal, klarna
	provider_payment_id = models.CharField(max_length=255, blank=True)
	amount = models.DecimalField(max_digits=10, decimal_places=2)
	# Currency should match the Order.currency. Default to EUR.
	currency = models.CharField(max_length=8, default="EUR")
	status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
	raw_response = models.JSONField(blank=True, null=True)
	# Provider refund id (if a refund was created) and timestamp for idempotency/audit
	provider_refund_id = models.CharField(max_length=255, blank=True, null=True)
	refunded_at = models.DateTimeField(blank=True, null=True)
	# When creating provider-side payment intents (e.g., Stripe PaymentIntent) we store
	# the client_secret (if applicable) so repeated start-payment calls can reuse it.
	provider_client_secret = models.CharField(max_length=255, blank=True, null=True)
	# Optional idempotency key provided by clients to deduplicate start-payment requests
	idempotency_key = models.CharField(max_length=255, blank=True, null=True, db_index=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.provider} {self.provider_payment_id} ({self.status})"

	def issue_refund(self, amount=None, idempotency_key=None):
		"""Issue a refund via the configured provider in an idempotent manner.

		- If `provider_refund_id` is already set, returns the stored `raw_response`.
		- Otherwise calls the provider refund API, stores provider_refund_id, raw_response, status and refunded_at.
		Raises exception on provider error.
		"""
		if self.provider_refund_id:
			# Already refunded (idempotent)
			return self.raw_response

		if self.provider != "stripe":
			raise NotImplementedError("Refunds only implemented for stripe in this helper")

		# Local import to avoid hard dependency at module import time
		import stripe
		from django.conf import settings

		stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)

		# Prepare refund params
		refund_kwargs = {"charge": self.provider_payment_id}
		if amount is not None:
			refund_kwargs["amount"] = int(amount * 100)

		# Use idempotency key via header if provided
		stripe_request_opts = {}
		if idempotency_key:
			stripe_request_opts = {"idempotency_key": idempotency_key}

		resp = stripe.Refund.create(**refund_kwargs, **({} if not stripe_request_opts else stripe_request_opts))

		# Attempt to extract a refund id from response
		refund_id = None
		if isinstance(resp, dict):
			refund_id = resp.get("id")
		else:
			# Some stripe libs return objects with id attribute
			refund_id = getattr(resp, "id", None)

		self.provider_refund_id = refund_id
		self.raw_response = resp
		self.status = PaymentRecord.STATUS_REFUNDED
		from django.utils import timezone
		self.refunded_at = timezone.now()
		self.save()
		return resp

class Reservation(models.Model):
	# Reservations used to lock items for a user during checkout (registered users only)
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservations")
	# optional link back to an order once checkout completes
	order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="reservations")

	# reference to a product; use generic relation to avoid app coupling
	content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
	object_id = models.PositiveIntegerField(null=True, blank=True)
	product_object = GenericForeignKey("content_type", "object_id")

	product_title = models.CharField(max_length=255)
	product_sku = models.CharField(max_length=64, blank=True)
	quantity = models.PositiveIntegerField(default=1)
	expires_at = models.DateTimeField()
	created_at = models.DateTimeField(auto_now_add=True)

	@classmethod
	def create_reservation(cls, user, product_title, product_sku, quantity=1, hours=4, **kwargs):
		expires = timezone.now() + timezone.timedelta(hours=hours)
		return cls.objects.create(user=user, product_title=product_title, product_sku=product_sku, quantity=quantity, expires_at=expires, **kwargs)

	def is_active(self):
		return timezone.now() < self.expires_at


class ProcessedEvent(models.Model):
	"""Record processed provider webhook event ids to make webhooks idempotent."""
	provider = models.CharField(max_length=64)
	event_id = models.CharField(max_length=255, unique=True)
	payload = models.JSONField(blank=True, null=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"{self.provider}:{self.event_id}"

from django.db import models

# Create your models here.
