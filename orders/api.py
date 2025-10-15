from rest_framework import status, views
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from .models import Order, PaymentRecord
from .serializers import OrderCreateSerializer


class CreateOrderView(views.APIView):
    """Create an order (guest or authenticated) without capturing payment yet.

    Frontend can call `start-payment/` to create a payment intent and
    capture payment.
    """

    # Only accept application/json requests for this endpoint.
    # Clients must POST JSON.
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        # Provide request in serializer context and require well-formed
        # JSON body.
        # We intentionally enforce strict JSON input here: the client must
        # POST a JSON
        # payload matching the serializer (including `items`).
        # No automatic guest_email
        # injection or raw-body parsing fallback is performed.
        data = request.data
        serializer = OrderCreateSerializer(
            data=data,
            context={
                "request": request,
                "user": getattr(request, "user", None),
                "is_authenticated": getattr(
                    getattr(request, "user", None), "is_authenticated", False
                ),
            },
        )
        serializer.is_valid(raise_exception=True)
        # Save will attach user if authenticated
        order = serializer.save()
        return Response(
            OrderCreateSerializer(order).data, status=status.HTTP_201_CREATED
        )


class StartPaymentView(views.APIView):
    """Start a payment for an order. This is a lightweight wrapper that creates
    a PaymentRecord and (optionally) creates a provider-side payment intent.
    Implementation here is provider-agnostic but includes Stripe example logic
    in `orders.payments`.
    """

    def post(self, request, order_id):
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        # Check for an idempotency key from the client to deduplicate
        # start-payment requests
        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY") or None

        # If a PaymentRecord exists for this order + idempotency_key,
        # return it (idempotent)
        if idempotency_key:
            existing = PaymentRecord.objects.filter(
                order=order, idempotency_key=idempotency_key).first()
            if existing:
                return Response({
                    "payment_id": existing.pk,
                    "client_secret": existing.provider_client_secret
                })

        # create a pending PaymentRecord
        payment = PaymentRecord.objects.create(
            order=order,
            provider="stripe",
            amount=order.total,
            currency=order.currency,
            status=PaymentRecord.STATUS_PENDING,
            idempotency_key=idempotency_key
        )

        # provider-specific: create payment intent
        from . import payments

        # Stripe expects amount in cents and lowercase currency code
        currency_code = (order.currency or "EUR").lower()
        client_secret = payments.create_stripe_payment_intent(
            amount=int(order.total * 100),
            currency=currency_code,
            metadata={"order_id": order.pk}
        )

        # store the client_secret for later idempotent calls
        payment.provider_client_secret = client_secret
        payment.save()

        return Response({
            "payment_id": payment.pk,
            "client_secret": client_secret
        })
