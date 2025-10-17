from django.views.generic import TemplateView
from django.shortcuts import redirect
from django.urls import reverse
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.decorators import method_decorator
from django.conf import settings
from django.core.mail import send_mail
from django.views.decorators.csrf import ensure_csrf_cookie
from urllib.parse import urlencode

from rest_framework import views, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from .serializers import SubscribeSerializer, UnsubscribeSerializer
from .models import Subscriber, SubscriptionEvent


class SubscribeView(views.APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        ser = SubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()
        locale = ser.validated_data.get("locale") or "en"
        source = ser.validated_data.get("source") or "footer_banner"

        sub, _ = Subscriber.objects.get_or_create(email=email)
        if sub.status == Subscriber.UNSUBSCRIBED:
            sub.status = Subscriber.PENDING
        if not sub.confirm_token:
            sub.confirm_token = get_random_string(40)
        sub.locale = locale
        sub.consent_source = source
        sub.save()

        SubscriptionEvent.objects.create(
            subscriber=sub, event_type="requested", details={"source": source}
        )

        confirm_path = reverse("newsletter:confirm")
        query = urlencode({"token": sub.confirm_token})
        confirm_link = request.build_absolute_uri(f"{confirm_path}?{query}")

        context = {"confirm_link": confirm_link}
        html_body = render_to_string("newsletter/emails/confirm_subscription.html", context)
        text_body = strip_tags(html_body)

        send_mail(
            subject="Confirm your subscription",
            message=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
            recipient_list=[email],
            html_message=html_body,
        )
        return Response({"detail": "Confirmation email sent"}, status=status.HTTP_200_OK)


class ConfirmView(views.APIView):
    def get(self, request):
        token = request.query_params.get("token")
        if not token:
            return redirect("newsletter:invalid")
        try:
            sub = Subscriber.objects.get(confirm_token=token)
        except Subscriber.DoesNotExist:
            return redirect("newsletter:invalid")
        sub.status = Subscriber.SUBSCRIBED
        sub.consent_at = timezone.now()
        sub.save()
        SubscriptionEvent.objects.create(subscriber=sub, event_type="confirmed")
        return redirect("newsletter:confirmed")


class UnsubscribeView(views.APIView):
    parser_classes = [JSONParser]

    def post(self, request):
        ser = UnsubscribeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        email = ser.validated_data["email"].lower()
        try:
            sub = Subscriber.objects.get(email=email)
        except Subscriber.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        sub.status = Subscriber.UNSUBSCRIBED
        sub.unsubscribed_at = timezone.now()
        sub.save()
        SubscriptionEvent.objects.create(subscriber=sub, event_type="unsubscribed")
        return Response({"detail": "Unsubscribed"}, status=status.HTTP_200_OK)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SubscribePageView(TemplateView):
    template_name = "newsletter/newsletter_subscribe.html"


class ConfirmedPageView(TemplateView):
    template_name = "newsletter/newsletter_confirmed.html"


class InvalidTokenPageView(TemplateView):
    template_name = "newsletter/newsletter_invalid.html"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class UnsubscribePageView(TemplateView):
    template_name = "newsletter/newsletter_unsubscribe.html"


class UnsubscribeDonePageView(TemplateView):
    template_name = "newsletter/newsletter_unsubscribe_done.html"
