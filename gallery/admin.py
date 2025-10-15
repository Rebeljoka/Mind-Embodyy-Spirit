from django.contrib import admin
from .models import Artist, Category, Painting, PaintingImage

# Register your models here.

admin.site.register(Artist)
admin.site.register(Category)
admin.site.register(Painting)
admin.site.register(PaintingImage)