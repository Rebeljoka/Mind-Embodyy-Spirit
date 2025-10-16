from django.conf import settings


def stripe_keys(request):
    """Add Stripe publishable key to template context."""
    return {
        'STRIPE_PUBLISHABLE_KEY': getattr(
            settings, 'STRIPE_PUBLISHABLE_KEY', ''
        ),
    }
