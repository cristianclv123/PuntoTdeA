from django.urls import path

from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.index, name='index'),
    path('list/', views.faq_list, name='list'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('chatbot/whatsapp/', views.whatsapp_webhook, name='whatsapp-webhook'),
]
