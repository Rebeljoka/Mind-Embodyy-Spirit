"""Minimal views for the orders app.

Keep this file tidy: group and alphabetize imports, add simple placeholders
and implement real views as features are developed.
"""

from django.http import HttpResponse


def index(request):
    """Simple placeholder view for the orders app."""
    return HttpResponse("Orders app is running.")
