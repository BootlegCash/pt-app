from django.urls import path

from . import views

app_name = "supplements"

urlpatterns = [
    path("", views.my_supplements, name="me"),
    path("coach/<uuid:client_uuid>/", views.coach_assign, name="coach_assign"),
    path("coach/toggle/<uuid:rec_uuid>/", views.coach_toggle, name="coach_toggle"),
]
