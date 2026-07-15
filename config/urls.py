from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from accounts.views import AdminLoginView

urlpatterns = [
    # Route the admin sign-in through the same throttled login as the portal.
    path("admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("profile/", include("profiles.urls")),
    path("exercises/", include("exercises.urls")),
    path("programs/", include("programs.urls")),
    path("workouts/", include("workouts.urls")),
    path("progress/", include("progress.urls")),
    path("nutrition/", include("nutrition.urls")),
    path("supplements/", include("supplements.urls")),
    path("coach/", include("coaching.urls")),
    path("files/", include("imports.urls")),
    path("calendar/", include("calendar_app.urls")),
]

# Public media only. Private files are served exclusively through
# authenticated download views — never via MEDIA_URL.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
