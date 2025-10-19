from django.shortcuts import render

from gallery.models import PaintingImage

# Create your views here.

def about_view(request):
    """
    Displays a list of events with dates that are
    either in the past or today.
    """
    painting = PaintingImage.objects

    # Create the context dictionary to pass to the template
    context = {
        'painting': painting,  # iterable of events for this page
    }

    return render(request, 'about.html', context)
