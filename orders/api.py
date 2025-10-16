from rest_framework import status, views
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from django.contrib.contenttypes.models import ContentType

from .models import Order, PaymentRecord, Cart, CartItem
from .serializers import OrderCreateSerializer


class CreateOrderView(views.APIView):
    """Create an order (guest or authenticated) without capturing payment yet.

    Frontend can call `start-payment/` to create a payment intent and
    capture payment.
    """

    # Only accept application/json requests for this endpoint.
    # Clients must POST JSON.
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        # Provide request in serializer context and require well-formed
        # JSON body.
        # We intentionally enforce strict JSON input here: the client must
        # POST a JSON
        # payload matching the serializer (including `items`).
        # No automatic guest_email
        # injection or raw-body parsing fallback is performed.
        data = request.data
        serializer = OrderCreateSerializer(
            data=data,
            context={
                "request": request,
                "user": getattr(request, "user", None),
                "is_authenticated": getattr(
                    getattr(request, "user", None), "is_authenticated", False
                ),
            },
        )
        serializer.is_valid(raise_exception=True)
        # Save will attach user if authenticated
        order = serializer.save()
        return Response(
            OrderCreateSerializer(order).data, status=status.HTTP_201_CREATED
        )


class StartPaymentView(views.APIView):
    """Start a payment for an order. This is a lightweight wrapper that creates
    a PaymentRecord and (optionally) creates a provider-side payment intent.
    Implementation here is provider-agnostic but includes Stripe example logic
    in `orders.payments`.
    """

    def post(self, request, order_id):
        try:
            order = Order.objects.get(pk=order_id)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        # Check for an idempotency key from the client to deduplicate
        # start-payment requests
        idempotency_key = request.META.get("HTTP_IDEMPOTENCY_KEY") or None

        # If a PaymentRecord exists for this order + idempotency_key,
        # return it (idempotent)
        if idempotency_key:
            existing = PaymentRecord.objects.filter(
                order=order, idempotency_key=idempotency_key
            ).first()
            if existing:
                return Response({
                    "payment_id": existing.pk,
                    "client_secret": existing.provider_client_secret
                })

        # create a pending PaymentRecord
        payment = PaymentRecord.objects.create(
            order=order,
            provider="stripe",
            amount=order.total,
            currency=order.currency,
            status=PaymentRecord.STATUS_PENDING,
            idempotency_key=idempotency_key
        )

        # provider-specific: create payment intent
        from . import payments

        # Stripe expects amount in cents and lowercase currency code
        currency_code = (order.currency or "EUR").lower()
        client_secret = payments.create_stripe_payment_intent(
            amount=int(order.total * 100),
            currency=currency_code,
            metadata={"order_id": order.pk}
        )

        # store the client_secret for later idempotent calls
        payment.provider_client_secret = client_secret
        payment.save()

        return Response({
            "payment_id": payment.pk,
            "client_secret": client_secret
        })


class AddToCartView(views.APIView):
    """Add an item to the shopping cart."""

    def post(self, request):
        # Get or create cart for user/session
        cart = self._get_or_create_cart(request)

        # Get product info from request
        content_type_id = request.data.get('content_type_id')
        object_id = request.data.get('object_id')
        quantity = request.data.get('quantity', 1)

        if not content_type_id or not object_id:
            return Response(
                {"detail": "content_type_id and object_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)
            if quantity < 1:
                return Response(
                    {"detail": "Quantity must be at least 1"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {"detail": "Invalid quantity"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get product details using generic relation
        try:
            content_type = ContentType.objects.get_for_id(content_type_id)
            product = content_type.get_object_for_this_type(pk=object_id)

            # Check if product has required attributes
            product_title = getattr(product, 'title', None)
            product_price = getattr(product, 'price', None)
            product_status = getattr(product, 'status', None)
            product_sku = getattr(product, 'sku', '')

            if not product_title or product_price is None:
                return Response(
                    {"detail": "Invalid product type"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if item is available
            if product_status and product_status != 'available':
                return Response(
                    {"detail": "Item is not available for purchase"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except ContentType.DoesNotExist:
            return Response(
                {"detail": "Invalid content type"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"Product not found: {str(e)}"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Add or update cart item
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            content_type_id=content_type_id,
            object_id=object_id,
            defaults={
                'product_title': product_title,
                'product_sku': product_sku,
                'unit_price': product_price,
                'quantity': quantity
            }
        )

        if not created:
            # Update quantity if item already exists
            cart_item.quantity += quantity
            cart_item.save()

        return Response({
            "cart_item_id": cart_item.pk,
            "quantity": cart_item.quantity,
            "total_items": cart.total_items,  # type: ignore
            "total_price": str(cart.total_price)  # type: ignore
        })

    def _get_or_create_cart(self, request):
        """Get or create cart for the current user/session."""
        if request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(
                user=request.user,
                defaults={}
            )
        else:
            # For anonymous users, use session
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key

            cart, created = Cart.objects.get_or_create(
                session_key=session_key,
                defaults={}
            )
        return cart


class CartView(views.APIView):
    """View and manage shopping cart contents."""

    def get(self, request):
        """Get cart contents."""
        cart = self._get_cart(request)
        if not cart:
            return Response({
                "items": [],
                "total_items": 0,
                "total_price": "0.00"
            })

        items = []
        for cart_item in cart.items.all():  # type: ignore
            items.append({
                "id": cart_item.pk,
                "product_title": cart_item.product_title,
                "product_sku": cart_item.product_sku,
                "unit_price": str(cart_item.unit_price),
                "quantity": cart_item.quantity,
                "total_price": str(cart_item.total_price),
                "content_type_id": cart_item.content_type_id,
                "object_id": cart_item.object_id
            })

        return Response({
            "items": items,
            "total_items": cart.total_items,
            "total_price": str(cart.total_price)
        })

    def _get_cart(self, request):
        """Get cart for the current user/session."""
        if request.user.is_authenticated:
            try:
                return Cart.objects.get(user=request.user)
            except Cart.DoesNotExist:
                return None
        else:
            session_key = request.session.session_key
            if session_key:
                try:
                    return Cart.objects.get(session_key=session_key)
                except Cart.DoesNotExist:
                    return None
        return None


class UpdateCartItemView(views.APIView):
    """Update quantity of an item in the cart."""

    def patch(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(pk=item_id)
        except CartItem.DoesNotExist:
            return Response(
                {"detail": "Cart item not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user owns this cart item
        cart = self._get_cart(request)
        if not cart or cart_item.cart != cart:
            return Response(
                {"detail": "Not authorized to modify this cart item"},
                status=status.HTTP_403_FORBIDDEN
            )

        quantity = request.data.get('quantity')
        if quantity is None or quantity < 0:
            return Response(
                {"detail": "Valid quantity is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity == 0:
            # Remove item if quantity is 0
            cart_item.delete()
            return Response({
                "removed": True,
                "total_items": cart.total_items,
                "total_price": str(cart.total_price)
            })

        cart_item.quantity = quantity
        cart_item.save()

        return Response({
            "cart_item_id": cart_item.pk,
            "quantity": cart_item.quantity,
            "total_price": str(cart_item.total_price),
            "cart_total_items": cart.total_items,
            "cart_total_price": str(cart.total_price)
        })

    def _get_cart(self, request):
        """Get cart for the current user/session."""
        if request.user.is_authenticated:
            try:
                return Cart.objects.get(user=request.user)
            except Cart.DoesNotExist:
                return None
        else:
            session_key = request.session.session_key
            if session_key:
                try:
                    return Cart.objects.get(session_key=session_key)
                except Cart.DoesNotExist:
                    return None
        return None


class RemoveFromCartView(views.APIView):
    """Remove an item from the cart."""

    def delete(self, request, item_id):
        try:
            cart_item = CartItem.objects.get(pk=item_id)
        except CartItem.DoesNotExist:
            return Response(
                {"detail": "Cart item not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user owns this cart item
        cart = self._get_cart(request)
        if not cart or cart_item.cart != cart:
            return Response(
                {"detail": "Not authorized to modify this cart item"},
                status=status.HTTP_403_FORBIDDEN
            )

        cart_item.delete()

        return Response({
            "removed": True,
            "total_items": cart.total_items,
            "total_price": str(cart.total_price)
        })

    def _get_cart(self, request):
        """Get cart for the current user/session."""
        if request.user.is_authenticated:
            try:
                return Cart.objects.get(user=request.user)
            except Cart.DoesNotExist:
                return None
        else:
            session_key = request.session.session_key
            if session_key:
                try:
                    return Cart.objects.get(session_key=session_key)
                except Cart.DoesNotExist:
                    return None
        return None
