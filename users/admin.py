from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import Profile


@admin.register(get_user_model())
class UserAdmin(admin.ModelAdmin):
    pass


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    pass
