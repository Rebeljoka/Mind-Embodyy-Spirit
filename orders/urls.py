from django.urls import path
from django.views.generic import TemplateView  # noqa: F401
from rest_framework.schemas import get_schema_view

from . import api
from . import views
from .webhooks import stripe_webhook
from .admin_api import RefundPaymentView


app_name = 'orders'

urlpatterns = [
    path("", views.index, name="orders-index"),
    path("cart/", views.cart_view, name="cart_page"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("payment/complete/", views.payment_complete_view,
         name="payment-complete"),
    path("order/<int:order_id>/success/", views.order_success_view,
         name="order_success"),
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
    # Cart API endpoints
    path("cart/view/", api.CartView.as_view(), name="orders-cart"),
    path("cart/add/", api.AddToCartView.as_view(), name="orders-add-to-cart"),
    path(
        "cart/item/<int:item_id>/",
        api.UpdateCartItemView.as_view(),
        name="orders-update-cart-item"
    ),
    path(
        "cart/item/<int:item_id>/remove/",
        api.RemoveFromCartView.as_view(),
        name="orders-remove-from-cart"
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
