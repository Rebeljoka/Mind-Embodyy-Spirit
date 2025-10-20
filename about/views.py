from django.shortcuts import render

from gallery.models import PaintingImage, Painting

# Create your views here.

def about_view(request):
    """Render the About page with an optional profile image and a dynamic
    selection of painting images from the gallery.

    - Profile image is stored in AboutData (singleton-style; use first if any).
    - Images are fetched dynamically from PaintingImage.
    """
    from .models import AboutData

    profile = AboutData.objects.first()

    #dynamic selection: latest 12 images from published paintings
    images_qs = (
        PaintingImage.objects
        .select_related('painting')
        .filter(painting__is_published=True)
        .order_by('-uploaded_at')
    )
    images = list(images_qs[:12])

    paintings = []
    if not images:
        # Fallback: show painting cover images when there are no PaintingImage entries
        paintings = list(
            Painting.objects
            .filter(is_published=True)
            .order_by('-date_created')
            .only('id', 'slug', 'title', 'cover_image')[:12]
        )

    context = {
        'profile': profile,
    'images': images,
    'paintings': paintings,
    }

    return render(request, 'about.html', context)
