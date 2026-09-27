"""
URL configuration for PuntoTdeA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import redirect
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from communications.meta_test_views import health as meta_test_health
from communications.meta_test_views import index as meta_test_index
from communications.meta_test_views import send_test_message as meta_test_send
from communications.meta_test_views import simulate_webhook as meta_test_simulate
from communications.meta_test_views import validate_credentials as meta_test_validate
from communications.webhooks.meta_webhook import whatsapp_webhook
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.profile_view, name='profile'),
    # Callback único configurado en Meta Developers para campañas y chatbot.
    path('api/whatsapp/webhook/', whatsapp_webhook, name='meta-whatsapp-webhook'),
    path(
        'api/whatsapp/health/',
        meta_test_health,
        name='meta-whatsapp-health',
    ),
    # Página de verificación de la integración. Solo para personal staff.
    path('whatsapp-prueba/', meta_test_index, name='meta-whatsapp-test'),
    path('whatsapp-prueba/enviar/', meta_test_send, name='meta-whatsapp-test-send'),
    path(
        'whatsapp-prueba/simular/',
        meta_test_simulate,
        name='meta-whatsapp-test-simulate',
    ),
    path(
        'whatsapp-prueba/validar/',
        meta_test_validate,
        name='meta-whatsapp-test-validate',
    ),

    path('api/cases/', include('cases.api.urls')),
    path('api/knowledge/', include('knowledge.api.urls')),

    # Documentación de la API (Swagger / Redoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Rutas principales de los módulos
    path('dashboard/', include('dashboard.urls')),
    path('bandeja/', include('cases.urls')),
    path('base-de-conocimiento/', include('knowledge.urls')),
    path('campanas/', include('communications.urls')),
    path('avisos/', include('announcements.urls')),

    # Redirecciones para compatibilidad con alias
    path('announcements/', lambda req: redirect('announcements:index', permanent=True)),
    path('communications/', lambda req: redirect('communications:index', permanent=True)),
    path('knowledge/', lambda req: redirect('knowledge:index', permanent=True)),
    path('casos/', lambda req: redirect('cases:bandeja', permanent=True)),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
