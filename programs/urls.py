from django.urls import path

from . import views

app_name = "programs"

urlpatterns = [
    path("current/", views.my_program, name="my_program"),
    path("builder/", views.builder_list, name="builder_list"),
    path("builder/new/", views.builder_create, name="builder_create"),
    path("builder/<uuid:program_uuid>/", views.builder_detail, name="builder_detail"),
    path("builder/<uuid:program_uuid>/edit/", views.builder_edit, name="builder_edit"),
    path("builder/<uuid:program_uuid>/copy/", views.builder_copy, name="builder_copy"),
    path(
        "builder/<uuid:program_uuid>/assign/<uuid:client_uuid>/",
        views.builder_assign, name="builder_assign",
    ),
    path("builder/week/<int:week_id>/edit/", views.week_edit, name="week_edit"),
    path("builder/week/<int:week_id>/copy/", views.week_copy, name="week_copy"),
    path("builder/week/<int:week_id>/day/new/", views.day_create, name="day_create"),
    path("builder/day/<int:day_id>/edit/", views.day_edit, name="day_edit"),
    path("builder/day/<int:day_id>/copy/", views.day_copy, name="day_copy"),
    path("builder/day/<int:day_id>/delete/", views.day_delete, name="day_delete"),
    path("builder/day/<int:day_id>/exercise/new/", views.exercise_create, name="exercise_create"),
    path("builder/exercise/<uuid:exercise_uuid>/edit/", views.exercise_edit, name="exercise_edit"),
    path("builder/exercise/<uuid:exercise_uuid>/delete/", views.exercise_delete, name="exercise_delete"),
    path(
        "builder/exercise/<uuid:exercise_uuid>/move/<str:direction>/",
        views.exercise_move, name="exercise_move",
    ),
]
