from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.core.validators import MinValueValidator, MaxValueValidator
# from taggit.managers import TaggableManager  # pip install django-taggit
from cloudinary.models import CloudinaryField


class StockItem(models.Model):
    """Simple stock/variant model used by orders to decrement inventory
    on payment.

    - `sku` is used as the lookup key from order item snapshots.
    - `stock` is a non-negative integer representing available units.
    """

    title = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    stock = models.PositiveIntegerField(default=0)
    # status for single-item availability (available, reserved, sold, archived)
    STATUS_AVAILABLE = "available"
    STATUS_RESERVED = "reserved"
    STATUS_SOLD = "sold"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_AVAILABLE, "Available"),
        (STATUS_RESERVED, "Reserved"),
        (STATUS_SOLD, "Sold"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_AVAILABLE,
        db_index=True
    )

    # mark true for one-of-a-kind items where status transitions apply
    is_unique = models.BooleanField(
        default=False,
        help_text="If true, single-copy item using status instead of stock."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.sku})" if self.sku else self.title


class Artist(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)
    portrait_image = models.ImageField(
        upload_to='artist/',
        blank=True,
        null=True,
    )
    is_primary = models.BooleanField(
        default=True,
        help_text="Mark the single site artist as primary",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=['is_primary'],
                condition=Q(is_primary=True),
                name='unique_primary_artist'
            )
        ]

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children',
    )
    created_at = models.DateTimeField(auto_now_add=True)  # Optional timestamp

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    # URL for category detail view
    def get_absolute_url(self):
        return reverse('gallery:category_detail', kwargs={'slug': self.slug})


class Painting(models.Model):
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('reserved', 'Reserved'),
        ('sold', 'Sold'),
        ('archived', 'Archived'),
    ]

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    cover_image = CloudinaryField('image', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    date_created = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='available',
        db_index=True,
    )
    is_published = models.BooleanField(default=True, db_index=True)

    # Link to the single site artist; protect from deletion
    artist = models.ForeignKey(
        Artist,
        on_delete=models.PROTECT,
        related_name='paintings',
        null=True,
        blank=True,
    )

    # Artwork metadata
    medium = models.CharField(max_length=120, blank=True)
    materials = models.CharField(max_length=255, blank=True)
    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1000),
            MaxValueValidator(9999),
        ],
    )
    dimensions = models.CharField(
        max_length=120,
        blank=True,
        help_text="e.g. 40 x 50 cm",
    )
    provenance = models.TextField(blank=True)
    exhibition_history = models.TextField(blank=True)

    # Flexible extra attributes
    metadata = models.JSONField(blank=True, null=True)

    # SEO
    meta_title = models.CharField(max_length=60, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)

    # Taxonomy and tags
    categories = models.ManyToManyField(
        'Category',
        blank=True,
        related_name='paintings',
    )
    # tags = TaggableManager(blank=True)

    class Meta:
        ordering = ['-date_created', 'title']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['is_published']),
            models.Index(fields=['-date_created']),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('gallery:painting_detail', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        # Auto-assign the primary artist if none provided
        if self.artist is None:
            try:
                self.artist = Artist.objects.get(is_primary=True)
            except Artist.DoesNotExist:
                pass
        super().save(*args, **kwargs)


class PaintingImage(models.Model):
    painting = models.ForeignKey(
        Painting,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = CloudinaryField('image')
    alt_text = models.CharField(
        max_length=255,
        help_text="Accessible description of the image",
    )
    caption = models.CharField(max_length=255, blank=True)
    credit = models.CharField(max_length=255, blank=True)
    license = models.CharField(max_length=120, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['painting', 'display_order'],
                name='unique_painting_image_order'
            )
        ]

    def __str__(self):
        return f"Image for {self.painting.title} ({self.display_order})"
