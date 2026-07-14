from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import LoginAttempt, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username", "email", "first_name", "last_name",
        "is_coach", "is_athlete", "is_staff", "is_active", "must_change_password",
    )
    list_filter = ("is_coach", "is_athlete", "is_staff", "is_active")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Roles", {"fields": ("is_coach", "is_athlete", "must_change_password", "uuid")}),
    )
    readonly_fields = ("uuid",)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "username", "email", "first_name", "last_name",
                "password1", "password2", "is_coach", "is_athlete",
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        creating = not change
        super().save_model(request, obj, form, change)
        if creating and obj.is_athlete:
            from profiles.models import AthleteProfile

            AthleteProfile.objects.get_or_create(user=obj)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("username", "ip_address", "created_at")
    readonly_fields = ("username", "ip_address", "created_at")
