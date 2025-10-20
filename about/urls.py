from django.urls import path
from . import views

# Namespace for reversing URLs as 'about:about'
app_name = 'about'

urlpatterns = [
    path('', views.about_view, name='about'),
]