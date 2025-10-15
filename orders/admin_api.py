from rest_framework import permissions, views, status
from rest_framework.response import Response
from django.conf import settings

from .models import PaymentRecord


class IsStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class RefundPaymentView(views.APIView):
    permission_classes = [IsStaff]

    def post(self, request, payment_id):
        try:
            payment = PaymentRecord.objects.get(pk=payment_id)
        except PaymentRecord.DoesNotExist:
            return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        # Only allow staff to trigger refunds
        if not request.user.is_staff:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        # Only support stripe for now
        if payment.provider != "stripe":
            return Response({"detail": "Provider not supported"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            import stripe

            stripe.api_key = getattr(settings, "STRIPE_SECRET_KEY", None)
            # Use model helper to perform an idempotent refund. Accept an optional Idempotency-Key header.
            idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY") or None
            resp = payment.issue_refund(amount=None, idempotency_key=idempotency_key)
            return Response({"refunded": True, "response": resp}, status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
