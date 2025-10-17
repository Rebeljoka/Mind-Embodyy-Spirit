from django.conf import settings
from django.db import models


class Subscriber(models.Model):
    PENDING = "pending"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SUBSCRIBED, "Subscribed"),
        (UNSUBSCRIBED, "Unsubscribed"),
        (BOUNCED, "Bounced"),
        (COMPLAINED, "Complained"),
    ]

    email = models.EmailField(unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    confirm_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    locale = models.CharField(max_length=8, blank=True)
    consent_text = models.CharField(max_length=255, blank=True)
    consent_source = models.CharField(max_length=64, blank=True)  # "footer_banner", "top_bar"
    consent_ip = models.GenericIPAddressField(null=True, blank=True)
    consent_user_agent = models.TextField(blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SubscriptionEvent(models.Model):
    subscriber = models.ForeignKey(Subscriber, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=32)  # "requested","confirmed","unsubscribed","bounce","complaint"
    details = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
