"""Minimal views for the orders app.

Keep this file tidy: group and alphabetize imports, add simple placeholders
and implement real views as features are developed.
"""

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from .models import Cart, Order


def index(request):
    """Simple placeholder view for the orders app."""
    return HttpResponse("Orders app is running.")


def get_cart_count(request):
    """API endpoint to get cart item count."""
    # Get cart for user/session
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            count = cart.total_items
        except Cart.DoesNotExist:
            count = 0
    else:
        session_key = request.session.session_key
        if session_key:
            try:
                cart = Cart.objects.get(session_key=session_key)
                count = cart.total_items
            except Cart.DoesNotExist:
                count = 0
        else:
            count = 0
    
    return JsonResponse({'count': count})


def cart_view(request):
    """Display the shopping cart contents."""
    # Get cart for user/session
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            cart = None
    else:
        session_key = request.session.session_key
        if session_key:
            try:
                cart = Cart.objects.get(session_key=session_key)
            except Cart.DoesNotExist:
                cart = None
        else:
            cart = None

    context = {
        'cart': cart,
        'cart_items': cart.items.all() if cart else [],  # type: ignore
        'total_items': cart.total_items if cart else 0,
        'total_price': cart.total_price if cart else 0,
    }

    return render(request, 'orders/cart.html', context)


def checkout_view(request):
    """Display checkout form for completing the order."""
    # Get cart for user/session
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
        except Cart.DoesNotExist:
            cart = None
    else:
        session_key = request.session.session_key
        if session_key:
            try:
                cart = Cart.objects.get(session_key=session_key)
            except Cart.DoesNotExist:
                cart = None
        else:
            cart = None

    # Check for payment completion
    client_secret = request.GET.get('payment_intent_client_secret')
    order_id = request.GET.get('order_id')

    if client_secret and order_id:
        # Payment processing mode
        try:
            order = Order.objects.get(id=order_id)
            context = {
                'order': order,
                'client_secret': client_secret,
                'payment_mode': True,
            }
            return render(request, 'orders/checkout.html', context)
        except Order.DoesNotExist:
            from django.shortcuts import redirect
            return redirect('orders:checkout')

    # Redirect to cart if empty
    if not cart or not cart.items.exists():  # type: ignore
        from django.shortcuts import redirect
        return redirect('orders:cart_page')

    if request.method == 'POST':
        return _process_checkout(request, cart)

    context = {
        'cart': cart,
        'cart_items': cart.items.all(),  # type: ignore
        'total_items': cart.total_items,
        'total_price': cart.total_price,
    }

    return render(request, 'orders/checkout.html', context)


def payment_complete_view(request):
    """Handle payment completion from Stripe."""
    from django.shortcuts import redirect
    from django.contrib import messages
    from . import payments

    # Get payment intent from URL parameters
    payment_intent_id = request.GET.get('payment_intent')
    client_secret = request.GET.get('payment_intent_client_secret')

    if not payment_intent_id:
        messages.error(request, 'Payment information missing.')
        return redirect('orders:checkout')

    try:
        # Retrieve payment intent from Stripe
        payment_intent = payments.stripe.PaymentIntent.retrieve(
            payment_intent_id)

        # Find the order using metadata
        order_id = payment_intent.metadata.get('order_id')
        if not order_id:
            messages.error(request, 'Order information not found.')
            return redirect('orders:checkout')

        order = Order.objects.get(id=order_id)
        payment_record = order.payments.first()  # Get the payment record

        if payment_intent.status == 'succeeded':
            # Payment successful
            payment_record.status = payment_record.STATUS_COMPLETED
            payment_record.provider_payment_id = payment_intent_id
            payment_record.save()

            # Update order status
            order.status = Order.STATUS_PAID
            order.save()

            messages.success(
                request,
                f'Payment successful! Order #{order.order_number}'
                ' has been confirmed.'
            )
            return redirect('orders:order_success', order_id=order.id)
        elif payment_intent.status == 'requires_payment_method':
            # Payment failed - redirect back to checkout
            payment_record.status = payment_record.STATUS_FAILED
            payment_record.save()

            messages.error(request, 'Payment failed. Please try again.')
            return redirect('orders:checkout')
        else:
            # Payment processing or other status
            messages.info(
                request,
                'Payment is being processed.'
                'You will receive a confirmation email shortly.'
            )
            return redirect('orders:checkout')

    except Exception as e:
        messages.error(request, f'Payment verification failed: {str(e)}')
        return redirect('orders:checkout')


def order_success_view(request, order_id):
    """Display order success page."""
    try:
        order = Order.objects.get(id=order_id)
        # Only show success page for the order owner or staff
        if not request.user.is_staff and order.user != request.user:
            from django.shortcuts import redirect
            return redirect('index')
    except Order.DoesNotExist:
        from django.shortcuts import redirect
        return redirect('index')

    context = {
        'order': order,
    }
    return render(request, 'orders/order_success.html', context)


def _process_checkout(request, cart):
    """Process the checkout form submission."""
    from django.contrib import messages
    from django.shortcuts import redirect
    from .serializers import OrderCreateSerializer
    from . import payments
    import stripe  # noqa: F401

    # Extract form data
    guest_email = request.POST.get('guest_email')
    shipping_data = {
        'full_name': request.POST.get('shipping_full_name'),
        'line1': request.POST.get('shipping_line1'),
        'line2': request.POST.get('shipping_line2', ''),
        'city': request.POST.get('shipping_city'),
        'region': request.POST.get('shipping_region', ''),
        'postal_code': request.POST.get('shipping_postal_code'),
        'country': request.POST.get('shipping_country'),
        'phone': request.POST.get('shipping_phone', ''),
    }

    # Check if billing address is different
    same_address = request.POST.get('same-address') == 'on'
    if same_address:
        billing_data = shipping_data.copy()
    else:
        billing_data = {
            'full_name': request.POST.get('billing_full_name'),
            'line1': request.POST.get('billing_line1'),
            'line2': request.POST.get('billing_line2', ''),
            'city': request.POST.get('billing_city'),
            'region': request.POST.get('billing_region', ''),
            'postal_code': request.POST.get('billing_postal_code'),
            'country': request.POST.get('billing_country'),
            'phone': request.POST.get('billing_phone', ''),
        }

    # Validate required fields
    required_shipping = ['full_name',
                         'line1', 'city', 'postal_code', 'country']
    for field in required_shipping:
        if not shipping_data.get(field):
            messages.error(request, f'Shipping {field.replace("_", " ")}'
                           ' is required.')
            return redirect('orders:checkout')

    if not same_address:
        required_billing = ['full_name', 'line1', 'city', 'postal_code',
                            'country']
        for field in required_billing:
            if not billing_data.get(field):
                messages.error(request, f'Billing {field.replace("_", " ")}'
                               ' is required.')
                return redirect('orders:checkout')

    # Create order data
    order_data = {
        'items': [],
        'shipping_address': shipping_data,
    }

    if not request.user.is_authenticated:
        if not guest_email:
            messages.error(request,
                           'Email address is required for guest checkout.')
            return redirect('orders:checkout')
        order_data['guest_email'] = guest_email

    # Convert cart items to order items
    for cart_item in cart.items.all():  # type: ignore
        order_data['items'].append({
            'product_title': cart_item.product_title,
            'product_sku': cart_item.product_sku,
            'unit_price': float(cart_item.unit_price),
            'quantity': cart_item.quantity,
        })

    # Create order
    try:
        serializer = OrderCreateSerializer(
            data=order_data,
            context={
                "request": request,
                "user": getattr(request, "user", None),
                "is_authenticated": getattr(
                    getattr(request, "user", None), "is_authenticated", False
                ),
            },
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Create billing address if different from shipping
        if not same_address:
            from .models import Address
            Address.objects.create(
                order=order,
                address_type=Address.BILLING,
                **billing_data
            )

        # Start payment
        from .models import PaymentRecord
        payment = PaymentRecord.objects.create(
            order=order,
            provider="stripe",
            amount=order.total,
            currency=order.currency,
            status=PaymentRecord.STATUS_PENDING,
        )

        # Create Stripe payment intent
        client_secret = payments.create_stripe_payment_intent(
            amount=int(order.total * 100),
            currency=order.currency.lower(),
            metadata={"order_id": order.pk}
        )

        payment.provider_client_secret = client_secret
        payment.save()

        # Clear cart after successful order creation
        cart.items.all().delete()  # type: ignore

        # Redirect to payment processing page with client_secret
        from django.urls import reverse
        payment_url = (
            f"{reverse('orders:checkout')}?"
            f"payment_intent_client_secret={client_secret}&order_id={order.id}"
        )
        return redirect(payment_url)

    except Exception as e:
        messages.error(request, f'Order creation failed: {str(e)}')
        return redirect('orders:checkout')
