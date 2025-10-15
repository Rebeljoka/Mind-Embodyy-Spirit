import os

# Default to non-debug unless explicitly set in the environment
os.environ.setdefault("DEBUG", "False")

# Only set SECRET_KEY if it's not already provided (prevents overwriting)
os.environ.setdefault(
    'SECRET_KEY',
    (
        'django-insecure-au7+aihfpmq(g8=kx6b^3&is-vjf7jsis='
        'yc5aw+yxu78k(lhz'
    ),
)

# Provide a DATABASE_URL for local development if not already set.
os.environ.setdefault(
    'DATABASE_URL',
    (
        'postgresql://neondb_owner:npg_NPV68QxlHoXE@ep-silent-grass-'
        'agkrhw0x.c-2.eu-central-1.aws.neon.tech/tabby_mumbo_herbs_722719'
    ),
)

# Provide a CLOUDINARY_URL for local development if not already set.
os.environ.setdefault(
    'CLOUDINARY_URL',
    (
        'cloudinary://122788721989999:'
        'DJ9NSmzC5eeBIpDsgy1hYYOWVTQ@dv2cq1oer'
    ),
)
