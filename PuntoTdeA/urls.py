"""
URL configuration for PuntoTdeA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),

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