from django.contrib import admin
from .models import StockItem


@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
	list_display = ("title", "sku", "stock", "created_at")
	search_fields = ("title", "sku")
	list_editable = ("stock",)
