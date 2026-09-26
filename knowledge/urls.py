from django.urls import path

from . import views

app_name = 'knowledge'

urlpatterns = [
    path('', views.index, name='index'),
    path('list/', views.faq_list, name='list'),
    path('search/', views.search, name='search'),
    path('ask/', views.ask, name='ask'),
    path('chatbot/', views.chatbot, name='chatbot'),
    path('chatbot/whatsapp/', views.whatsapp_webhook, name='whatsapp-webhook'),
    path('reindex-academic-calendar/', views.reindex_academic_calendar, name='reindex-academic-calendar'),
]
