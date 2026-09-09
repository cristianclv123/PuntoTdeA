from django.urls import path
from . import views

app_name = 'announcements'  # <-- Esta línea registra el namespace
urlpatterns = [
    path('', views.index, name='index'),
]