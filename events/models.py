from django.db import models

from django.core.validators import MinValueValidator
from datetime import date

from cloudinary.models import CloudinaryField

# Create your models here.
from django.db import models
from django.db.models import Q
from django.urls import reverse


class Event(models.Model):
    
    """Simple events model to allow superusers the ability to add upcoming events.

    - validators used to prevent user from adding an event in the past.
    
    """
    
    event_name = models.CharField(max_length=255)
    location = models.CharField(max_length=200)
    event_date = models.DateField(
        help_text="Please select a date from today onwards.",
        validators=[
            MinValueValidator(
                date.today,
                message="Event date cannot be in the past."
            )
        ]
    )
    
    poster = CloudinaryField(
        'image', 
        null=True, 
        blank=True,
        help_text="Optional: Upload an event poster."
    )
    
    def __str__(self):
        return f"{self.event_name} on {self.event_date}"