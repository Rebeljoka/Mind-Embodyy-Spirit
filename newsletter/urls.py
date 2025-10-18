# newsletter/urls.py
from django.urls import path
from .views import (
    SubscribeView, ConfirmView, UnsubscribeView,
    SubscribePageView, ConfirmedPageView, InvalidTokenPageView,
    UnsubscribeDonePageView, UnsubscribePageView,
)

app_name = "newsletter"
urlpatterns = [
     # API POST
    path("subscribe/", SubscribeView.as_view(), name="subscribe"),
    # GET page-> newsletter_subscribe.html
    path("subscribe/page/", SubscribePageView.as_view(), name="subscribe_page"),
    # GET token -> redirect to confirmed or invalid
    path("confirm/", ConfirmView.as_view(), name="confirm"),
    # GET page-> newsletter_confirmed.html
    path("confirmed/", ConfirmedPageView.as_view(), name="confirmed"),
    # GET page-> newsletter_invalid.html
    path("invalid/", InvalidTokenPageView.as_view(), name="invalid"),
    # API POST
    path("unsubscribe/", UnsubscribeView.as_view(), name="unsubscribe"),
    path("unsubscribe/page/", UnsubscribePageView.as_view(), name="unsubscribe_page"),
    # GET page-> newsletter_unsubscribe_done.html
    path("unsubscribe/done/", UnsubscribeDonePageView.as_view(), name="unsubscribe_done"),
]
