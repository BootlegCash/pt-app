from django.urls import path

from . import views

app_name = "profiles"

urlpatterns = [
    path("", views.my_profile, name="me"),
    path("measurements/", views.my_measurements, name="measurements"),
    path("photo/<uuid:user_uuid>/", views.profile_photo, name="photo"),
]
