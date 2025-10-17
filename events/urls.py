from django.urls import path
from . import views


app_name = 'events'

urlpatterns = [
    path('', views.event_list_view, name='events'),
        path('<int:pk>/edit/', views.event_edit_view, name='event_edit'),
        path('<int:pk>/delete/', views.event_delete, name='event_delete'),
]
