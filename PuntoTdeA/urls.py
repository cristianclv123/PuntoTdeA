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

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('api/cases/', include('cases.api.urls')),

    # Rutas principales en español (únicas que registran el namespace)
    path('bandeja/', include('cases.urls')),
    path('base-de-conocimiento/', include('knowledge.urls')),
    path('campanas/', include('communications.urls')),
    path('avisos/', include('announcements.urls')),

    # Redirecciones para compatibilidad con alias en inglés (evita el warning W005)
    path('announcements/', lambda req: redirect('announcements:index', permanent=True)),
    path('communications/', lambda req: redirect('communications:index', permanent=True)),
    path('knowledge/', lambda req: redirect('knowledge:index', permanent=True)),
    path('casos/', lambda req: redirect('cases:bandeja', permanent=True)),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from .views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    path('anuncios/', include('announcements.urls')),
    # 1. Ruta del Módulo Core / Landing Page (Punto TdeA)
    path('', home, name='home'),
# Rutas de los otros 4 Módulos
    path('announcements/', include('announcements.urls')),
    #path('cases/', include('cases.urls')),
    path('communications/', include('communications.urls')),
    path('knowledge/', include('PuntoTdeA.knowledge.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

