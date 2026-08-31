from django.urls import path

from . import views

app_name = "cases"

urlpatterns = [
    path("", views.bandeja, name="bandeja"),
    path("<int:case_id>/", views.caso_detail, name="detail"),
]
