from django.contrib import admin
from django.contrib import messages
from . import models


@admin.register(models.Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number", "user", "guest_email", "status",
        "total", "stock_shortage", "created_at"
    )
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "guest_email", "user__email")
    actions = ["mark_shipped", "mark_refunded"]

    @admin.action(description="Mark selected orders as shipped")
    def mark_shipped(self, request, queryset):
        updated = queryset.update(status=models.Order.STATUS_SHIPPED)

        messages.success(request, f"Marked {updated} orders as shipped")

    def issue_refunds_and_mark_refunded(self, request, queryset):
        """Issue refunds for payments on selected orders and mark refunded."""

        success = 0
        errors = []
        for order in queryset:
            # related_name on PaymentRecord is 'payments'
            payments = order.payments.all()
            order_refunded = True
            for p in payments:
                try:
                    p.issue_refund()
                except Exception as exc:
                    order_refunded = False
                    errors.append(f"Order {order.pk}: {exc}")
            if order_refunded:
                order.status = models.Order.STATUS_REFUNDED
                order.save()
                success += 1

        if success:
            messages.success(request, f"Marked {success} orders as refunded")
        if errors:
            messages.error(request, "Errors: " + "; ".join(errors))

    @admin.action(description="Issue refunds and mark orders refunded")
    def mark_refunded(self, request, queryset):
        """Issue refunds for payments on selected orders and mark refunded."""
        from django.contrib import messages
        success = 0
        errors = []
        for order in queryset:
            # related_name on PaymentRecord is 'payments'
            payments = order.payments.all()
            order_refunded = True
            for p in payments:
                try:
                    p.issue_refund()
                except Exception as exc:
                    order_refunded = False
                    errors.append(f"Order {order.pk}: {exc}")
            if order_refunded:
                order.status = models.Order.STATUS_REFUNDED
                order.save()
                success += 1

        if success:
            messages.success(request, f"Marked {success} orders as refunded")
        if errors:
            messages.error(request, "Errors: " + "; ".join(errors))

    mark_refunded.short_description = "Issue refunds and mark orders refunded"


@admin.register(models.OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("product_title", "order", "unit_price", "quantity")
    search_fields = ("product_title", "product_sku")


@admin.register(models.PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display = (
        "provider", "provider_payment_id", "order",
        "amount", "status", "created_at"
    )
    list_filter = ("provider", "status")


@admin.action(description="Issue refund for selected payments")
def issue_refund(modeladmin, request, queryset):
    """Admin action to issue refunds for selected payments."""
    from django.contrib import messages
    success = 0
    errors = []
    for payment in queryset:
        try:
            if not payment.provider_payment_id:
                errors.append(
                    f"Payment {payment.pk} has no provider_payment_id"
                )
                continue

            # Use PaymentRecord.issue_refund to ensure idempotency
            idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY") or None
            payment.issue_refund(idempotency_key=idempotency_key)
            success += 1
        except Exception as exc:
            errors.append(str(exc))

    if success:
        messages.success(request, f"Issued refunds for {success} payments")
    if errors:
        messages.error(request, "Errors: " + "; ".join(errors))


PaymentRecordAdmin.actions = [issue_refund]


@admin.register(models.Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "user", "product_title", "quantity",
        "expires_at", "created_at"
    )
    list_filter = ("expires_at",)


@admin.register(models.Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = (
        "order", "address_type", "full_name",
        "line1", "city", "postal_code"
    )
