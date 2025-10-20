from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('gallery/', views.gallery_management, name='gallery_management'),
    path('gallery/upload/', views.upload_artwork, name='upload_artwork'),
    path('gallery/edit/<int:artwork_id>/',
         views.edit_artwork, name='edit_artwork'),
    path('gallery/delete/<int:artwork_id>/',
         views.delete_artwork, name='delete_artwork'),
    path('gallery/<int:artwork_id>/add-image/',
         views.add_artwork_image, name='add_artwork_image'),
    path('gallery/image/<int:image_id>/delete/',
         views.delete_artwork_image, name='delete_artwork_image'),
    path('events/', views.events_management, name='events_management'),
    path('events/create/', views.create_event, name='create_event'),
    path('events/edit/<int:event_id>/',
         views.edit_event, name='edit_event'),
    path('events/delete/<int:event_id>/',
         views.delete_event, name='delete_event'),
    path('orders/', views.orders_management, name='orders_management'),
    path(
        'orders/<int:order_id>/details/',
        views.order_details,
        name='order_details'
    ),
    path('orders/<int:order_id>/update-status/',
         views.update_order_status, name='update_order_status'),
     path('artist-admin/', views.frontend_admin, name='artist_admin'),
     path('about/', views.about_management, name='about_management'),
]
