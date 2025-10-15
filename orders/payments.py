import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def create_stripe_payment_intent(amount: int, currency: str = "usd", metadata: dict | None = None) -> str:
    """Create a Stripe PaymentIntent and return the client_secret.

    amount is in cents.
    This function expects `stripe` to be installed and `settings.STRIPE_SECRET_KEY` to be set.
    In the absence of stripe (or in tests) it will return a fake client secret.
    """
    try:
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(amount=amount, currency=currency, metadata=metadata or {})
        return intent.client_secret
    except Exception as exc:
        logger.exception("Stripe not available or failed to create intent: %s", exc)
        # Fallback for local development / tests
        return "test_client_secret"


def verify_stripe_event(payload: bytes, sig_header: str) -> dict | None:
    """Verify and parse a Stripe webhook event. Returns the event dict or None on failure."""
    try:
        import stripe

        stripe.api_key = settings.STRIPE_SECRET_KEY
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        return event
    except Exception:
        logger.exception("Failed to verify stripe webhook event")
        return None
