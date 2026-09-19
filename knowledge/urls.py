from django.urls import path
from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.index, name='index'),
<<<<<<< Updated upstream
]
=======
    path('', views.index, name='list'),
    path('search/', views.search, name='search'),
    path('ask/', views.ask, name='ask'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('chatbot/whatsapp/', views.whatsapp_webhook, name='whatsapp-webhook'),
]
>>>>>>> Stashed changes
