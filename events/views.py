from django.shortcuts import render, get_object_or_404

from .models import Event

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
    