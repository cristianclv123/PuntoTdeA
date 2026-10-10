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

from communications.meta_console_views import config as meta_console_config
from communications.meta_console_views import health as meta_console_health
from communications.meta_console_views import index as meta_console_index
from communications.meta_console_views import send_test_message as meta_console_send
from communications.meta_console_views import send_test_template as meta_console_send_template
from communications.meta_console_views import validate_credentials as meta_console_validate
from communications.meta_console_views import window_status as meta_console_window
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
        meta_console_health,
        name='meta-whatsapp-health',
    ),
    # Consola de verificación de la integración. Solo para personal staff.
    path('whatsapp-prueba/', meta_console_index, name='meta-whatsapp-test'),
    path('whatsapp-prueba/enviar/', meta_console_send, name='meta-whatsapp-test-send'),
    path(
        'whatsapp-prueba/enviar-plantilla/',
        meta_console_send_template,
        name='meta-whatsapp-test-send-template',
    ),
    path(
        'whatsapp-prueba/ventana/',
        meta_console_window,
        name='meta-whatsapp-test-window',
    ),
    path(
        'whatsapp-prueba/validar/',
        meta_console_validate,
        name='meta-whatsapp-test-validate',
    ),
    path(
        'whatsapp-configuracion/',
        meta_console_config,
        name='meta-whatsapp-config',
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
