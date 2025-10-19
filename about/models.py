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
        help_text="Optional: Upload a a featured video.")
    
    def __str__(self):
        return "About Profile"