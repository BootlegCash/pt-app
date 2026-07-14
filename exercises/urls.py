from django.urls import path

from . import views

app_name = "exercises"

urlpatterns = [
    path("", views.library, name="library"),
    path("<slug:slug>/", views.detail, name="detail"),
]
