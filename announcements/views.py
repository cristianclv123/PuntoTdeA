from django.shortcuts import render, redirect
from .models import Announcement

def index(request):
    if request.method == 'POST':
        # Capturamos los datos de los inputs del HTML
        title = request.POST.get('title')
        body_text = request.POST.get('body')  # Viene del name="body" del HTML de tu compañera
        notice_type = request.POST.get('type') # 'urgente' o 'informativo'
        image_file = request.FILES.get('image') #esto es para la imagen
        
        # Determinamos si es urgente basándonos en lo que seleccionó el usuario
        is_urgent = True if notice_type == 'urgente' else False

        # Guardamos en la base de datos usando el campo 'content' 
        Announcement.objects.create(
            title=title,
            content=body_text,  # Mapeamos 'body' del HTML al campo 'content' del modelo
            image=image_file,
            is_urgent=is_urgent
        )
        return redirect('announcements:index')

   
    #Listado de avisos
    announcements = Announcement.objects.all().order_by('-created_at')
    urgent_announcements = Announcement.objects.filter(is_urgent=True).order_by('-created_at')
    
    context = {
        'announcements': announcements,
        'urgent_announcements': urgent_announcements,
    }
    
    return render(request, 'announcements/avisos.html', context)
