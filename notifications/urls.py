from django.urls import path

from notifications import views

app_name = "notifications"

urlpatterns = [
    path("api/", views.list_notifications, name="list"),
    path("api/leer-todas/", views.mark_all_read, name="mark-all-read"),
    path("api/<int:notification_id>/leer/", views.mark_read, name="mark-read"),
]
