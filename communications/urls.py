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
    path("", views.campaigns, name="campaigns"),
    path("", views.campaigns, name="index"),
    path("nueva/", views.campaign_new, name="campaign_new"),
    path("detalle/", views.campaign_detail, name="campaign_detail"),
    path("audiencias/", views.segments, name="segments"),
    path("test-send/", views.test_send, name="test_send"),
    path("api/test-send/", viewsets.TestSendAPIView.as_view(), name="api-test-send"),

    # Plantillas de Meta (la fuente de verdad) y borradores locales.
    path(
        "api/templates/meta/",
        viewsets.MetaTemplateListView.as_view(),
        name="api-meta-templates",
    ),
    path(
        "api/templates/meta/<str:meta_id>/",
        viewsets.MetaTemplateDetailView.as_view(),
        name="api-meta-template-detail",
    ),

    # Compatibilidad con rutas anteriores
    path("campanas/", views.campaigns),
    path("campanas/nueva/", views.campaign_new),
    path("campanas/detalle/", views.campaign_detail),

    # API interna, consumida por el BFF
    path("api/", include(router.urls)),
]
