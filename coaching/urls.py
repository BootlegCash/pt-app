from django.urls import path

from . import views

app_name = "coaching"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("clients/", views.client_list, name="client_list"),
    path("clients/<uuid:client_uuid>/", views.client_detail, name="client_detail"),
    path("clients/<uuid:client_uuid>/notes/", views.client_notes_save, name="client_notes_save"),
    path("clients/<uuid:client_uuid>/profile/", views.client_profile_edit, name="client_profile_edit"),
    path("clients/<uuid:client_uuid>/measurements/", views.client_measurements, name="client_measurements"),
    path("clients/<uuid:client_uuid>/maxes/", views.client_maxes, name="client_maxes"),
    path("clients/<uuid:client_uuid>/calendar/", views.client_calendar, name="client_calendar"),
    path("clients/<uuid:client_uuid>/history/", views.client_history, name="client_history"),
    path(
        "clients/<uuid:client_uuid>/session/<uuid:session_uuid>/",
        views.client_session_detail, name="client_session_detail",
    ),
    path("progressions/", views.progression_approvals, name="progression_approvals"),
    path("progressions/<uuid:rec_uuid>/approve/", views.progression_approve, name="progression_approve"),
    path("progressions/<uuid:rec_uuid>/reject/", views.progression_reject, name="progression_reject"),
    path("pain/", views.pain_flags, name="pain_flags"),
    path("pain/<uuid:report_uuid>/reviewed/", views.pain_mark_reviewed, name="pain_mark_reviewed"),
    path("users/new/", views.create_user, name="create_user"),
    path("relationships/<uuid:relationship_uuid>/end/", views.relationship_end, name="relationship_end"),
]
