from django.db import models

from cloudinary.models import CloudinaryField

# Create your models here.

class AboutData(models.Model):
    profile_image = CloudinaryField(
        'image', 
        null=True, 
        blank=True,
        help_text="Optional: Upload a profile picture."
    )

    video = CloudinaryField(
        resource_type='video',
        null=True, 
        blank=True,
        help_text="Optional: Upload a featured video."
    )

    featured_artworks = models.ManyToManyField(
        'gallery.Painting',
        blank=True,
        related_name='featured_in_about',
        help_text="Select artworks to feature in the about section."
    )

    biography = models.TextField(
        blank=True,
        help_text="Artist biography or personal story."
    )

    mission_statement = models.TextField(
        blank=True,
        help_text="Mission statement or artistic philosophy."
    )

    artist_statement = models.TextField(
        blank=True,
        help_text="Artist statement or creative process description."
    )

    def __str__(self):
        return "About Profile"