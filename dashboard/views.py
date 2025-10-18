from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Max
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from gallery.models import Painting, Category, Artist, PaintingImage
from events.models import Event
from orders.models import Order
from .models import ActivityLog

# Constants
PAINTINGS_PER_PAGE = 12
ORDERS_PER_PAGE = 20


def generate_unique_slug(title, exclude_id=None):
    """Generate a unique slug from title, ensuring no duplicates exist."""
    from django.utils.text import slugify

    base_slug = slugify(title)
    slug = base_slug
    counter = 1

    # Build query to check for existing slugs
    query = Painting.objects.filter(slug=slug)
    if exclude_id:
        query = query.exclude(id=exclude_id)

    while query.exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
        # Rebuild query for new slug
        query = Painting.objects.filter(slug=slug)
        if exclude_id:
            query = query.exclude(id=exclude_id)

    return slug


def log_activity(request, action, item_type, item_id, item_name,
                 description=""):
    """Log an administrative activity."""
    try:
        ActivityLog.objects.create(
            user=request.user,
            action=action,
            item_type=item_type,
            item_id=item_id,
            item_name=item_name,
            description=description,
            ip_address=get_client_ip(request),
        )
    except Exception:
        # Don't let logging failures break the main functionality
        pass


def get_client_ip(request):
    """Get the client's IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def is_staff_or_superuser(user):
    """Check if user is staff or superuser"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_or_superuser)
def dashboard_home(request):
    """Main dashboard home page with overview statistics"""
    # Get statistics
    total_paintings = Painting.objects.count()
    available_paintings = Painting.objects.filter(status='available').count()
    total_events = Event.objects.count()
    upcoming_events = Event.objects.filter(
        event_date__gte=timezone.now().date()).count()
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()

    # Get recent activities (last 10 activities)
    recent_activities = ActivityLog.objects.select_related('user')[:10]

    context = {
        'total_paintings': total_paintings,
        'available_paintings': available_paintings,
        'total_events': total_events,
        'upcoming_events': upcoming_events,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'recent_activities': recent_activities,
    }

    return render(request, 'dashboard/dashboard_home.html', context)


# Gallery Management Views
@login_required
@user_passes_test(is_staff_or_superuser)
def gallery_management(request):
    """List all paintings with management options"""
    paintings = Painting.objects.all().order_by('-date_created')

    # Pagination
    paginator = Paginator(paintings, PAINTINGS_PER_PAGE)  # Items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'paintings': page_obj,
    }

    return render(request, 'dashboard/gallery_management.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def upload_artwork(request):
    """Upload new artwork"""
    if request.method == 'POST':
        # Handle form submission
        title = request.POST.get('title')
        description = request.POST.get('description')
        price = request.POST.get('price')
        status = request.POST.get('status', 'available')
        cover_image = request.FILES.get('cover_image')

        # Generate unique slug from title
        slug = generate_unique_slug(title)

        try:
            painting = Painting.objects.create(
                title=title,
                slug=slug,
                description=description,
                price=price,
                status=status,
                cover_image=cover_image,
                date_created=timezone.now(),
            )
            messages.success(
                request,
                f'Artwork "{painting.title}" uploaded successfully!'
            )
            # Log the activity
            log_activity(
                request, 'create', 'painting', painting.id,
                painting.title, f'Uploaded new artwork with status: {status}'
            )
            return redirect('dashboard:gallery_management')
        except IntegrityError:
            messages.error(request, 'Artwork with this title already exists')
        except ValidationError as e:
            messages.error(request, f'Invalid data: {str(e)}')
        except (ValueError, TypeError) as e:
            messages.error(request, f'Invalid data provided: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error uploading artwork: {str(e)}')

    # Get categories and artists for form
    categories = Category.objects.all()
    artists = Artist.objects.all()

    context = {
        'categories': categories,
        'artists': artists,
    }

    return render(request, 'dashboard/upload_artwork.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_artwork(request, artwork_id):
    """Edit existing artwork"""
    painting = get_object_or_404(Painting, id=artwork_id)

    if request.method == 'POST':
        # Handle form submission
        # Store original title for slug comparison
        original_title = painting.title
        new_title = request.POST.get('title', '').strip()
        if not new_title:
            messages.error(request, 'Title is required')
            return redirect('dashboard:edit_artwork', artwork_id=artwork_id)

        painting.title = new_title
        painting.description = request.POST.get('description', '').strip()

        # Handle price conversion safely
        price_str = request.POST.get('price', '').strip()
        if not price_str:
            messages.error(request, 'Price is required')
            return redirect('dashboard:edit_artwork', artwork_id=artwork_id)

        try:
            from decimal import Decimal
            painting.price = Decimal(price_str)
        except (ValueError, TypeError):
            messages.error(request, f'Invalid price format: {price_str}')
            return redirect('dashboard:edit_artwork', artwork_id=artwork_id)

        painting.status = request.POST.get('status', painting.status)

        # Generate slug from title if title changed
        if new_title != original_title:
            painting.slug = generate_unique_slug(new_title, painting.id)

        if 'cover_image' in request.FILES:
            painting.cover_image = request.FILES['cover_image']

        try:
            painting.save()
            # More specific success message based on what changed
            old_status = request.POST.get('old_status')
            if old_status and painting.status != old_status:
                messages.success(
                    request,
                    f'Artwork "{painting.title}" '
                    f'status updated to {painting.status}!'
                )
                log_activity(
                    request, 'status_change', 'painting', painting.id,
                    painting.title,
                    f'Status changed from {old_status} to {painting.status}'
                )
            else:
                messages.success(
                    request,
                    f'Artwork "{painting.title}" updated successfully!'
                )
                log_activity(
                    request, 'update', 'painting', painting.id,
                    painting.title, 'Artwork details updated'
                )
            return redirect('dashboard:gallery_management')
        except IntegrityError:
            messages.error(request, 'Artwork with this title already exists')
        except ValidationError as e:
            messages.error(request, f'Invalid data: {str(e)}')
        except Exception as e:
            messages.error(request, f'Error updating artwork: {str(e)}')
            return redirect('dashboard:edit_artwork', artwork_id=artwork_id)

    # Get additional images
    additional_images = painting.images.all().order_by('display_order')

    context = {
        'painting': painting,
        'additional_images': additional_images,
    }

    return render(request, 'dashboard/edit_artwork.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_artwork(request, artwork_id):
    """Delete artwork"""
    painting = get_object_or_404(Painting, id=artwork_id)

    try:
        painting.delete()
        messages.success(
            request, f'Artwork "{painting.title}" deleted successfully!'
        )
        log_activity(
            request, 'delete', 'painting', painting.id,
            painting.title, 'Artwork permanently deleted'
        )
    except Exception as e:
        messages.error(request, f'Error deleting artwork: {str(e)}')

    return redirect('dashboard:gallery_management')


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def add_artwork_image(request, artwork_id):
    """Add additional image to artwork"""
    painting = get_object_or_404(Painting, id=artwork_id)

    if 'image' in request.FILES:
        image_file = request.FILES['image']
        alt_text = request.POST.get('alt_text', '')
        caption = request.POST.get('caption', '')

        # Get the next display order
        max_order = painting.images.aggregate(
            Max('display_order'))['display_order__max'] or 0
        display_order = max_order + 1

        try:
            PaintingImage.objects.create(
                painting=painting,
                image=image_file,
                alt_text=alt_text,
                caption=caption,
                display_order=display_order,
            )
            messages.success(request, 'Additional image added successfully!')
        except Exception as e:
            messages.error(request, f'Error adding image: {str(e)}')

    return redirect('dashboard:edit_artwork', artwork_id=artwork_id)


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_artwork_image(request, image_id):
    """Delete additional image from artwork"""
    image = get_object_or_404(PaintingImage, id=image_id)
    artwork_id = image.painting.id

    try:
        image.delete()
        messages.success(request, 'Image deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting image: {str(e)}')

    return redirect('dashboard:edit_artwork', artwork_id=artwork_id)


# Events Management Views
@login_required
@user_passes_test(is_staff_or_superuser)
def events_management(request):
    """List all events with management options"""
    events = Event.objects.all().order_by('-event_date')

    context = {
        'events': events,
    }

    return render(request, 'dashboard/events_management.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def create_event(request):
    """Create new event"""
    if request.method == 'POST':
        event_name = request.POST.get('event_name')
        location = request.POST.get('location')
        event_date = request.POST.get('event_date')
        poster = request.FILES.get('poster')

        try:
            event = Event.objects.create(
                event_name=event_name,
                location=location,
                event_date=event_date,
                poster=poster,
            )
            messages.success(
                request, f'Event "{event.event_name}" created successfully!'
            )
            log_activity(
                request, 'create', 'event', event.id,
                event.event_name, f'Event created for {event.event_date}'
            )
            return redirect('dashboard:events_management')
        except Exception as e:
            messages.error(request, f'Error creating event: {str(e)}')

    return render(request, 'dashboard/create_event.html')


@login_required
@user_passes_test(is_staff_or_superuser)
def edit_event(request, event_id):
    """Edit existing event"""
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        event.event_name = request.POST.get('event_name', event.event_name)
        event.location = request.POST.get('location', event.location)
        event.event_date = request.POST.get('event_date', event.event_date)

        if 'poster' in request.FILES:
            event.poster = request.FILES['poster']

        try:
            event.save()
            messages.success(
                request, f'Event "{event.event_name}" updated successfully!'
            )
            log_activity(
                request, 'update', 'event', event.id,
                event.event_name, 'Event details updated'
            )
            return redirect('dashboard:events_management')
        except Exception as e:
            messages.error(request, f'Error updating event: {str(e)}')

    context = {
        'event': event,
    }

    return render(request, 'dashboard/edit_event.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
@require_POST
def delete_event(request, event_id):
    """Delete event"""
    event = get_object_or_404(Event, id=event_id)

    try:
        event.delete()
        messages.success(
            request, f'Event "{event.event_name}" deleted successfully!'
        )
        log_activity(
            request, 'delete', 'event', event.id,
            event.event_name, 'Event permanently deleted'
        )
    except Exception as e:
        messages.error(request, f'Error deleting event: {str(e)}')

    return redirect('dashboard:events_management')


# Orders Management Views
@login_required
@user_passes_test(is_staff_or_superuser)
def orders_management(request):
    """List all orders with management options"""
    orders = Order.objects.all().order_by('-created_at')

    # Pagination
    paginator = Paginator(orders, ORDERS_PER_PAGE)  # Items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'orders': page_obj,
    }

    return render(request, 'dashboard/orders_management.html', context)


@login_required
@user_passes_test(is_staff_or_superuser)
def order_details(request, order_id):
    """Get detailed order information for AJAX requests"""
    order = get_object_or_404(Order, id=order_id)

    # Get order items
    items = []
    for item in order.order_items.all():
        items.append({
            'id': item.id,
            'product_title': item.product_title,
            'product_sku': item.product_sku,
            'unit_price': str(item.unit_price),
            'quantity': item.quantity,
            'total_price': str(item.total_price),
        })

    # Get addresses
    shipping_address = None
    billing_address = None
    for address in order.addresses.all():
        if address.address_type == 'shipping':
            shipping_address = {
                'full_name': address.full_name,
                'line1': address.line1,
                'line2': address.line2,
                'city': address.city,
                'region': address.region,
                'postal_code': address.postal_code,
                'country': address.country,
                'phone': address.phone,
            }
        elif address.address_type == 'billing':
            billing_address = {
                'full_name': address.full_name,
                'line1': address.line1,
                'line2': address.line2,
                'city': address.city,
                'region': address.region,
                'postal_code': address.postal_code,
                'country': address.country,
                'phone': address.phone,
            }

    # Get payment information
    payments = []
    for payment in order.payments.all():
        payments.append({
            'provider': payment.provider,
            'provider_payment_id': payment.provider_payment_id,
            'amount': str(payment.amount),
            'currency': payment.currency,
            'status': payment.status,
            'created_at': payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        })

    order_data = {
        'id': order.id,
        'order_number': order.order_number,
        'status': order.status,
        'status_display': order.get_status_display(),
        'total': str(order.total),
        'currency': order.currency,
        'stock_shortage': order.stock_shortage,
        'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': order.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
        'customer': {
            'name': (order.user.get_full_name() if order.user
                     else 'Guest Customer'),
            'email': order.user.email if order.user else order.guest_email,
            'username': order.user.username if order.user else None,
        },
        'items': items,
        'shipping_address': shipping_address,
        'billing_address': billing_address,
        'payments': payments,
    }

    return JsonResponse(order_data)


@login_required
@user_passes_test(is_staff_or_superuser)
def update_order_status(request, order_id):
    """Update order status"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    order = get_object_or_404(Order, id=order_id)
    new_status = request.POST.get('status')

    # Validate status
    valid_statuses = ['paid', 'processing', 'shipped', 'cancelled', 'refunded']
    if new_status not in valid_statuses:
        return JsonResponse({'error': 'Invalid status'}, status=400)

    old_status = order.status
    order.status = new_status
    order.save()

    # Log the status change
    log_activity(
        request, 'status_change', 'order', order.id,
        f'Order {order.order_number}',
        f'Status changed from {old_status} to {new_status}'
    )

    return JsonResponse({
        'success': True,
        'order_id': order.id,
        'old_status': old_status,
        'new_status': new_status,
        'status_display': order.get_status_display()
    })


# Front-end artist/admin page (single-page entry for superusers/staff)
@login_required
@user_passes_test(is_staff_or_superuser)
def frontend_admin(request):
    """Front-facing admin page that provides a simplified single-page
    interface for the artist to manage gallery, events and orders.

    The page uses an iframe to load existing dashboard sections so we can
    deliver a unified front-end experience without duplicating backend
    logic.
    """
    return render(request, 'dashboard/artist_admin.html')
