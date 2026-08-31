from django.shortcuts import render

def home(request):
    """
    Vista principal (Landing Page) para el proyecto Punto TdeA.
    """
    return render(request, 'index.html')