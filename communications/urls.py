from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("", views.campaigns, name="campaigns"),
    path("", views.campaigns, name="index"),
]
