from django.urls import path

from . import views

app_name = "communications"

urlpatterns = [
    path("", views.campaigns, name="campaigns"),
    path("", views.campaigns, name="index"),
    path("nueva/", views.campaign_new, name="campaign_new"),
    path("detalle/", views.campaign_detail, name="campaign_detail"),
    path("audiencias/", views.segments, name="segments"),
    path("interacciones/", views.interactions, name="interactions"),
    # Compatibilidad con rutas anteriores
    path("campanas/", views.campaigns),
    path("campanas/nueva/", views.campaign_new),
    path("campanas/detalle/", views.campaign_detail),
]
