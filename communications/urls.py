from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("", views.index, name="index"),
    path("campanas/", views.campaigns, name="campaigns"),
    path("campanas/nueva/", views.campaign_new, name="campaign_new"),
    path("campanas/detalle/", views.campaign_detail, name="campaign_detail"),
    path("audiencias/", views.segments, name="segments"),
    path("interacciones/", views.interactions, name="interactions"),
]