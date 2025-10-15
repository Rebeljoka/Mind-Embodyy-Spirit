from django.contrib import admin
from .models import StockItem


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ("title", "sku", "stock", "created_at")
    search_fields = ("title", "sku")
    list_editable = ("stock",)
from .models import Artist, Category, Painting, PaintingImage

# Register your models here.

admin.site.register(Artist)
admin.site.register(Category)
admin.site.register(Painting)
admin.site.register(PaintingImage)
