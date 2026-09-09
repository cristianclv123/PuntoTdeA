from django.contrib import admin
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
    path('knowledge/', include('knowledge.urls')),
]