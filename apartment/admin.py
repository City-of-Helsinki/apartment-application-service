from django.contrib import admin

from .models import ProjectExtraData


@admin.register(ProjectExtraData)
class ProjectExtraDataAdmin(admin.ModelAdmin):
    list_display = (
        "project_uuid",
        "offer_message_intro",
        "offer_message_content",
        "created_at",
        "updated_at",
    )
