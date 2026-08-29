from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

def anuncios(request):
    return render(request, 'announcements/index.html')