from django.shortcuts import render, get_object_or_404

from .models import Events

from datetime import date

# Create your views here.

def event_list_view(request):
    """
    Displays a list of events with dates that are 
    either in the past or today.
    """
    # Filter events where the event_date is less than or equal to today
    events_to_display = Events.objects.filter(
        event_date__lte=date.today()
    ).order_by('-event_date') 

    # Create the context dictionary to pass to the template
    context = {
        'events': events_to_display
    }
    
    return render(request, 'event_list.html', context)
    