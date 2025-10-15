from django.http import JsonResponse
from django.conf import settings


DEFAULT_JSON_ONLY_VIEWS = ("orders-create",)


class RequireJSONForOrdersCreate:
    """Route-name based middleware to require JSON for configured views.

    This middleware uses `request.resolver_match.view_name` to match named
    routes and only enforces the JSON requirement for POST requests to those
    views. The list of view names can be configured via
    `settings.ORDERS_JSON_ONLY_VIEWS` (iterable of view name strings).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Normal middleware flow — perform view-level checks in process_view
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Only enforce for POST requests
        if request.method != "POST":
            return None
        resolver_match = getattr(request, "resolver_match", None)
        view_name = getattr(resolver_match, "view_name", None)

        # Read configured list at request time so tests that use  # noqa # noqa 
        # override_settings can change behavior without middleware  # noqa
        # needing re-instantiation. This ensures that tests using  # noqa
        # override_settings can change behavior dynamically.
        json_only_views = tuple(
            getattr(settings, "ORDERS_JSON_ONLY_VIEWS", DEFAULT_JSON_ONLY_VIEWS))  # noqa

        if view_name in json_only_views:
            content_type = request.META.get("CONTENT_TYPE", "") or ""
            if not content_type.startswith(  # noqa
                "application/json"  # noqa
            ):
                return JsonResponse(
                    {
                        "detail": (
                            (
                                "This endpoint accepts application/json only. "
                                "Please POST valid JSON. "
                                "Set Content-Type: application/json and send a "  # noqa
                                "JSON body matching the Orders API."
                            )
                        ),
                    },
                    status=415,
                )

        return None
