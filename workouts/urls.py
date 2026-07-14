from django.urls import path

from . import views

app_name = "workouts"

urlpatterns = [
    path("start/<uuid:scheduled_uuid>/", views.start_session, name="start"),
    path("log/<uuid:session_uuid>/", views.logger, name="logger"),
    path("log/<uuid:session_uuid>/autosave/", views.autosave_set, name="autosave"),
    path("log/<uuid:session_uuid>/remove-set/", views.remove_extra_set, name="remove_extra_set"),
    path("log/<uuid:session_uuid>/complete/", views.complete_session, name="complete"),
    path("session/<uuid:session_uuid>/", views.session_detail, name="detail"),
    path("history/", views.history, name="history"),
    path("exercise/<slug:slug>/", views.exercise_history_page, name="exercise_history"),
]
