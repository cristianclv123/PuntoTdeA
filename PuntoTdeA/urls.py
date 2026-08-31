"""
URL configuration for PuntoTdeA project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('bandeja/', include('cases.urls')),
    path('base-de-conocimiento/', include('knowledge.urls')),
    path('campanas/', include('communications.urls')),
    path('avisos/', include('announcements.urls')),
]
