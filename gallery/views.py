from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView  # noqa: F401
from .models import Painting, Category, Artist  # noqa: F401


def gallery_collection(request):
    """Display all published paintings in the gallery."""
    paintings = (
        Painting.objects.filter(is_published=True)
        .prefetch_related('images', 'categories', 'artist')
        .order_by('-date_created')
    )

    # Get filter parameters
    category_slug = request.GET.get('category')
    status_filter = request.GET.get('status')

    if category_slug:
        paintings = paintings.filter(categories__slug=category_slug)

    if status_filter:
        paintings = paintings.filter(status=status_filter)

    context = {
        'paintings': paintings,
        'categories': Category.objects.all(),
        'selected_category': category_slug,
        'selected_status': status_filter,
    }

    return render(request, 'gallery/collection.html', context)


def painting_detail(request, slug):
    """Display a single painting with all its images."""
    try:
        painting = get_object_or_404(
            Painting.objects.prefetch_related(
                'images', 'categories', 'artist'
            ),
            slug=slug,
        )

        # Get the content type ID for Painting model
        from django.contrib.contenttypes.models import ContentType
        painting_content_type = ContentType.objects.get_for_model(Painting)

        context = {
            'painting': painting,
            'painting_content_type_id': painting_content_type.id,
        }

        return render(request, 'gallery/painting_detail.html', context)
    except Exception as e:
        # Temporary debugging - print the error
        print(f"Error in painting_detail: {type(e).__name__}: {str(e)}")
        raise
