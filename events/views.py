from django.shortcuts import render,redirect, get_object_or_404
from django.contrib import messages

from .models import Event
from .forms import EventForm


from django.utils import timezone
from django.core.paginator import Paginator

# Create your views here.

def event_list_view(request):
    """
    Displays a list of events with dates that are 
    either in the past or today.
    """
    # Show upcoming events (today and future), ordered soonest first
    today = timezone.localdate()
    events_qs = Event.objects.filter(
        event_date__gte=today
    ).order_by('event_date')

    # Paginate the events list (3 per page)
    paginator = Paginator(events_qs, 3)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Create the context dictionary to pass to the template
    context = {
        'events': page_obj,  # iterable of events for this page
        'page_obj': page_obj,
    }
    
    return render(request, 'event_list.html', context)


def event_edit_view(request, pk: int):
    """Handle event edits via modal form; superuser only.

    Expects POST with fields event_name, location, event_date, poster.
    Redirects back to events list with a flash message.
    """
    if not request.user.is_superuser:
        messages.error(request, "You do not have permission to edit events.")
        return redirect('events:events')

    event = get_object_or_404(Event, pk=pk)

    if request.method == 'POST':
        form = EventForm(request.POST, request.FILES, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated!')
        else:
            # Collect first error for quick feedback
            first_error = next(iter(form.errors.values()))[0] if form.errors else 'Please correct the errors.'
            messages.error(request, f'Error updating event: {first_error}')
        return redirect('events:events')

    # Default: we don't render a separate page for GET; return to list
    return redirect('events:events')
    