from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from users.models import DjangoUser, DrupalUser, Profile


@admin.register(get_user_model())
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "profile_or_user_first_name",
        "profile_or_user_last_name",
        "is_django_salesperson",
        "is_drupal_salesperson",
    )
    list_display_links = ("email",)


@admin.register(DrupalUser)
class DrupalUserAdmin(DjangoUserAdmin):
    list_display = ("email", "get_full_name", "is_drupal_salesperson")
    list_display_links = ("email",)

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(profile=None)

    def get_full_name(self, obj):
        return obj.profile.full_name

    get_full_name.admin_order_field = "profile"
    get_full_name.short_description = _("Full name")


@admin.register(DjangoUser)
class SalesUIUserAdmin(DjangoUserAdmin):
    list_display = ("email", "full_name", "is_django_salesperson")
    list_display_links = ("email",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(profile=None)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    pass
