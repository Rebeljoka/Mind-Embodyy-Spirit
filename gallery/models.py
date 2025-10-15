from django.db import models


class StockItem(models.Model):
	"""Simple stock/variant model used by orders to decrement inventory on payment.

	- `sku` is used as the lookup key from order item snapshots.
	- `stock` is a non-negative integer representing available units.
	"""

	title = models.CharField(max_length=255)
	sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
	stock = models.PositiveIntegerField(default=0)
	# status for single-item availability (available, reserved, sold, archived)
	STATUS_AVAILABLE = "available"
	STATUS_RESERVED = "reserved"
	STATUS_SOLD = "sold"
	STATUS_ARCHIVED = "archived"

	STATUS_CHOICES = [
		(STATUS_AVAILABLE, "Available"),
		(STATUS_RESERVED, "Reserved"),
		(STATUS_SOLD, "Sold"),
		(STATUS_ARCHIVED, "Archived"),
	]

	status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_AVAILABLE, db_index=True)

	# mark true for one-of-a-kind paintings where status transitions (reserved/sold) apply
	is_unique = models.BooleanField(default=False, help_text="If true, item is single-copy and uses status transitions instead of stock counts")

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return f"{self.title} ({self.sku})" if self.sku else self.title
