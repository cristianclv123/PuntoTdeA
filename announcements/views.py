from django.shortcuts import render
from .models import Announcement

def index(request):
    # Consultamos todos los anuncios de la base de datos, ordenados del más reciente al más antiguo
    announcements = Announcement.objects.all().order_by('-created_at')
    
    # Filtramos específicamente los que son urgentes para cumplir con la HU-08
    urgent_announcements = Announcement.objects.filter(is_urgent=True).order_by('-created_at')
    
    context = {
        'announcements': announcements,
        'urgent_announcements': urgent_announcements,
    }
    
    return render(request, 'announcements/avisos.html', context)
