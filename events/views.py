from django.shortcuts import render, get_object_or_404

from .models import Event

from django.utils import timezone

# Create your views here.

def event_list_view(request):
    """
    Displays a list of events with dates that are 
    either in the past or today.
    """
    # Show upcoming events (today and future), ordered soonest first
    today = timezone.localdate()
    events_to_display = Event.objects.filter(
        event_date__gte=today
    ).order_by('event_date') 

    # Create the context dictionary to pass to the template
    context = {
        'events': events_to_display
    }
    
    return render(request, 'event_list.html', context)
    