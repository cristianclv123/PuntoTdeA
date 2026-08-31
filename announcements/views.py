from django.shortcuts import render

# Create your views here.
from django.shortcuts import render

def anuncios(request):
    return render(request, 'announcements/index.html')

from django.http import HttpResponse

def index(request):
    return HttpResponse("<h1>Módulo de Anuncios</h1><p>En construcción</p>")

from django.http import HttpResponse

def index(request):
    return HttpResponse("<h1>Módulo de Anuncios</h1><p>En construcción</p>")