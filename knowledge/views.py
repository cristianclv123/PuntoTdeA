from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse

def index(request):
    return HttpResponse("<h1>Módulo de Conocimiento</h1><p>En construcción</p>")