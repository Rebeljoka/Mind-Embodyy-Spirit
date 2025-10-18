"""
Dashboard app models.

This app doesn't define its own models. Instead, it provides views and
templates for managing models from other apps (gallery, events, orders).
This keeps the dashboard as a pure management interface without duplicating
data structures.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ActivityLog(models.Model):
    """Log of administrative activities for audit and monitoring."""

    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('status_change', 'Status Changed'),
        ('login', 'Logged In'),
        ('refund', 'Refunded'),
    ]

    ITEM_TYPE_CHOICES = [
        ('painting', 'Painting'),
        ('event', 'Event'),
        ('order', 'Order'),
        ('user', 'User'),
        ('system', 'System'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    item_id = models.PositiveIntegerField(null=True, blank=True)
    item_name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        return (
            f"{self.user.username} "
            f"{self.get_action_display()} "
            f"{self.item_name}"
        )


# No models are defined here - this app provides views and templates
# for managing models from other Django apps in the project.
