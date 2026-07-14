from django.urls import path

from . import views

app_name = "nutrition"

urlpatterns = [
    path("", views.my_nutrition, name="me"),
    path("checkin/", views.checkin, name="checkin"),
    path("coach/<uuid:client_uuid>/", views.coach_calculator, name="coach_calculator"),
]
