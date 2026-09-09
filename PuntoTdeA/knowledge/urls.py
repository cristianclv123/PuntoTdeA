from django.urls import path

from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.index, name='index'),
    path('search/', views.search, name='search'),
    path('ask/', views.ask, name='ask'),
]