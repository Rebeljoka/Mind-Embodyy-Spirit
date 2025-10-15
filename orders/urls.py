from django.urls import path
from rest_framework.schemas import get_schema_view

from . import api
from .webhooks import stripe_webhook
from .admin_api import RefundPaymentView

urlpatterns = [
    path("create/", api.CreateOrderView.as_view(), name="orders-create"),
    path(
        "start-payment/<int:order_id>/",
        api.StartPaymentView.as_view(),
        name="orders-start-payment"
    ),
    path("webhook/", stripe_webhook, name="orders-webhook"),
    path(
        "refund/<int:payment_id>/",
        RefundPaymentView.as_view(),
        name="orders-refund",
    ),
    path(
        "schema/",
        get_schema_view(
            title="Orders API",
            description="Schema for orders endpoints"
        ),
        name="orders-schema"
    ),
]
