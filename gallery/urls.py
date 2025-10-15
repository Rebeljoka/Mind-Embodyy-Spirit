from django.urls import path
from . import views

app_name = 'gallery'

urlpatterns = [
    path('', views.gallery_collection, name='collection'),
    path(
        'painting/<slug:slug>/',
        views.painting_detail,
        name='painting_detail'
    ),
]
