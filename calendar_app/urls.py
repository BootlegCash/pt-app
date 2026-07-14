from django.urls import path

from . import views

app_name = "calendar_app"

urlpatterns = [
    path("", views.my_week, name="week"),
    path("google/connect/", views.google_connect, name="google_connect"),
    path("google/callback/", views.google_callback, name="google_callback"),
    path("google/disconnect/", views.google_disconnect, name="google_disconnect"),
    path("google/sync/", views.google_sync, name="google_sync"),
    path("month/", views.my_month, name="month"),
    path("day/<uuid:session_uuid>/", views.day_detail, name="day_detail"),
    path("coach/<uuid:client_uuid>/add/", views.coach_session_create, name="coach_session_create"),
    path("coach/session/<uuid:session_uuid>/edit/", views.coach_session_edit, name="coach_session_edit"),
    path("coach/session/<uuid:session_uuid>/delete/", views.coach_session_delete, name="coach_session_delete"),
]
