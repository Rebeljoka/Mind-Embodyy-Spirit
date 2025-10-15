from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .payments import verify_stripe_event
from .models import PaymentRecord, Order, ProcessedEvent
from django.db import transaction
from gallery.models import StockItem
from django.core.mail import send_mail
from django.conf import settings


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    event = verify_stripe_event(payload, sig_header)
    if not event:
        return HttpResponse(status=400)

    event_type = event.get("type")
    data = event.get("data", {}).get("object", {})

    # idempotency: skip if we've seen this provider event id before
    event_id = event.get("id")
    if event_id:
        if ProcessedEvent.objects.filter(event_id=event_id).exists():
            return JsonResponse({"received": True, "skipped": True})
        # record the event as processed
        try:
            ProcessedEvent.objects.create(
                provider="stripe",
                event_id=event_id,  # noqa: E501
                payload=event,
            )
        except Exception:
            # if create fails (race condition) proceed — we'll still try to
            # process but avoid throwing
            pass

    # handle payment succeeded
    if event_type == "payment_intent.succeeded":
        # find payment by metadata order_id if available
        order_id = data.get("metadata", {}).get("order_id")
        if order_id:
            try:
                order = Order.objects.get(pk=order_id)
                # mark payment record(s) for the order as succeeded
                PaymentRecord.objects.filter(
                    order=order,
                    provider_payment_id=data.get("id"),
                ).update(
                    status=PaymentRecord.STATUS_SUCCEEDED,
                    provider_payment_id=data.get("id"),
                    raw_response=data,
                )

                # Decrement stock atomically. If any product lacks stock, mark
                # order.stock_shortage
                shortage = False
                # Build mapping of product SKUs to ordered quantities
                # from snapshot order items
                sku_map = {
                    item.product_sku: item.quantity
                    for item in order.items if item.product_sku  # type: ignore  # noqa
                }
                if sku_map:
                    with transaction.atomic():
                        products = list(
                            StockItem.objects.select_for_update().filter(
                                sku__in=list(sku_map.keys())
                            )
                        )
                        prod_map = {p.sku: p for p in products}
                        for sku, qty in sku_map.items():
                            stock_item = prod_map.get(sku)
                            if not stock_item:
                                shortage = True
                                continue
                            # If this is a unique single-item,
                            # use status transitions
                            if getattr(stock_item, 'is_unique', False):
                                # Only handle single-item sales when qty == 1
                                if qty == 1:
                                    if stock_item.status in (
                                        StockItem.STATUS_AVAILABLE,
                                        StockItem.STATUS_RESERVED,
                                    ):
                                        stock_item.status = (
                                            StockItem.STATUS_SOLD
                                        )
                                        stock_item.save()
                                    else:
                                        # requested qty > 1 for single-item SKU
                                        # cannot fulfill
                                        shortage = True
                                else:
                                    # requested qty > 1 for a single-item SKU
                                    # -> cannot fulfill
                                    shortage = True
                            else:
                                # For multi-quantity items, decrement
                                # the stock count accordingly.
                                if stock_item.stock >= qty:  # noqa: E501
                                    stock_item.stock = stock_item.stock - qty
                                    stock_item.save()
                                else:
                                    shortage = True

                if shortage:
                    # Mark order as having stock shortage.
                    # This indicates insufficient stock for
                    # fulfillment.
                    order.stock_shortage = True
                order.status = (
                    Order.STATUS_PROCESSING
                )
                order.save()

                # Send an order confirmation email
                # (synchronous, small MVP behavior)
                try:
                    subject = f"Order {order.order_number} confirmation"
                    body = (
                        f"Thank you for your order {order.order_number}. "
                        f"Status: {order.status}. "
                        f"Total: {order.total} {order.currency}"
                    )
                    recipient = order.guest_email or (
                        order.user.email if order.user else None
                    )
                    if recipient:
                        send_mail(
                            subject,
                            body,
                            getattr(
                                settings,
                                'DEFAULT_FROM_EMAIL',
                                'noreply@example.com'
                            ),
                            [recipient]
                        )
                except Exception:
                    # email sending failure should not prevent webhook
                    # processing
                    pass
            except Order.DoesNotExist:
                pass

    # handle refund
    if (
        event_type == "charge.refunded"
        or event_type == "charge.refund.updated"
    ):
        # TODO: mark refund on payment record and order
        pass

    return JsonResponse({"received": True})
