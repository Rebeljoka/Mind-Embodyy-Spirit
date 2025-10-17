from django import forms
from django.utils import timezone
from .models import Event


class EventForm(forms.ModelForm):
    """Improved Event form with:
    - Tailwind/DaisyUI-friendly widgets and placeholders
    - Dynamic min date (today) on the date input
    - Extra validation for future date and poster file (type/size)
    """

    MAX_UPLOAD_SIZE_MB = 5

    class Meta:
        model = Event
        fields = ("event_name", "location", "event_date", "poster")
        labels = {
            "event_name": "Event name",
            "location": "Location",
            "event_date": "Event date",
            "poster": "Poster (optional)",
        }
        help_texts = {
            "event_date": "Choose a date from today onwards.",
            "poster": "JPEG/PNG/WEBP up to 5MB.",
        }
        widgets = {
            "event_name": forms.TextInput(
                attrs={
                    "placeholder": "e.g. Art & Craft",
                    "class": "input input-bordered w-full",
                    "autocomplete": "off",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "placeholder": "Venue, City",
                    "class": "input input-bordered w-full",
                    "autocomplete": "off",
                }
            ),
            "event_date": forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "input input-bordered w-full",
                }
            ),
            "poster": forms.ClearableFileInput(
                attrs={
                    "accept": ".jpg,.jpeg,.png,.webp,image/*",
                    "class": "file-input file-input-bordered w-full",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set dynamic min date for the date input to today (local date)
        today_str = timezone.localdate().isoformat()
        if "min" not in self.fields["event_date"].widget.attrs:
            self.fields["event_date"].widget.attrs["min"] = today_str

        # Ensure all widgets have consistent base classes if none were set
        for name, field in self.fields.items():
            css = field.widget.attrs.get("class", "").strip()
            if not css:
                # Fallback classes by input type
                if isinstance(field.widget, forms.ClearableFileInput):
                    field.widget.attrs["class"] = "file-input file-input-bordered w-full"
                elif isinstance(field.widget, forms.DateInput):
                    field.widget.attrs["class"] = "input input-bordered w-full"
                else:
                    field.widget.attrs["class"] = "input input-bordered w-full"

    def clean_event_date(self):
        event_date = self.cleaned_data.get("event_date")
        if not event_date:
            return event_date
        today = timezone.localdate()
        if event_date < today:
            raise forms.ValidationError("Event date cannot be in the past.")
        return event_date

    def clean_poster(self):
        poster = self.cleaned_data.get("poster")
        if not poster:
            return poster

        # File size check
        max_bytes = self.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if hasattr(poster, "size") and poster.size > max_bytes:
            raise forms.ValidationError(
                f"File too large. Max size is {self.MAX_UPLOAD_SIZE_MB}MB."
            )

        # Content type check (best-effort)
        ctype = getattr(poster, "content_type", "") or ""
        if ctype and not ctype.startswith("image/"):
            raise forms.ValidationError("Please upload a valid image file.")

        return poster