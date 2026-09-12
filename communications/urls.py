from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views, viewsets

app_name = "communications"

router = DefaultRouter()
router.register("contacts", viewsets.ContactViewSet, basename="api-contacts")
router.register("templates", viewsets.MessageTemplateViewSet, basename="api-templates")
router.register("segments", viewsets.AudienceSegmentViewSet, basename="api-segments")
router.register("campaigns", viewsets.CampaignViewSet, basename="api-campaigns")

urlpatterns = [
    path("", views.index, name="index"),
    path("campanas/", views.campaigns, name="campaigns"),
    path("campanas/nueva/", views.campaign_new, name="campaign_new"),
    path("campanas/detalle/", views.campaign_detail, name="campaign_detail"),
    path("audiencias/", views.segments, name="segments"),
    path("interacciones/", views.interactions, name="interactions"),

    # API interna, consumida por el BFF (ver communications/permissions.py)
    path("api/", include(router.urls)),
]