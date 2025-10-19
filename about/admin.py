from django.contrib import admin
from .models import AboutData


@admin.register(AboutData)
class AboutDataAdmin(admin.ModelAdmin):
	list_display = ("id", "has_profile_image")

	def has_profile_image(self, obj: AboutData) -> bool:
		return bool(getattr(obj, "profile_image", None))

	has_profile_image.boolean = True  # display as a boolean icon in admin
