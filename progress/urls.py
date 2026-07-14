from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("maxes/", views.maxes, name="maxes"),
    path("charts/", views.charts_page, name="charts"),
    path("volume/", views.volume_page, name="volume"),
    path("api/chart/<str:name>/", views.chart_data, name="chart_data"),
]
