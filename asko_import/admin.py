from django.contrib.admin import ModelAdmin, register, RelatedOnlyFieldListFilter
from django.utils.timezone import localtime

from .models import AsKoImportLogEntry, AsKoLink


class ReadOnlyModelAdmin(ModelAdmin):
    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False


class FormattedCreatedAtMixin(ModelAdmin):
    def formatted_created_at(self, obj):
        return localtime(obj.created_at).strftime("%Y-%m-%d %H:%M:%S.%f")

    formatted_created_at.admin_order_field = "created_at"
    formatted_created_at.short_description = AsKoLink._meta.get_field(
        "created_at"
    ).verbose_name


class FormattedTimestampsMixin(FormattedCreatedAtMixin):
    def formatted_updated_at(self, obj):
        return localtime(obj.updated_at).strftime("%Y-%m-%d %H:%M:%S.%f")

    formatted_updated_at.admin_order_field = "updated_at"
    formatted_updated_at.short_description = AsKoLink._meta.get_field(
        "updated_at"
    ).verbose_name


@register(AsKoLink)
class AsKoLinkAdmin(ReadOnlyModelAdmin, FormattedTimestampsMixin):
    list_display = (
        "formatted_created_at",
        "formatted_updated_at",
        "object_type",
        "asko_id",
        "object_id_int",
        "object_id_uuid",
    )

    list_filter = [
        ("object_type", RelatedOnlyFieldListFilter),
    ]

    search_fields = ("asko_id", "object_id_int", "object_id_uuid")


@register(AsKoImportLogEntry)
class AsKoImportLogEntryAdmin(ReadOnlyModelAdmin, FormattedCreatedAtMixin):
    list_display = (
        "formatted_created_at",
        "content_type",
        "asko_id",
        "level",
        "message",
    )
    list_filter = [
        "level",
        ("content_type", RelatedOnlyFieldListFilter),
        "message_template",
    ]
    search_fields = ("message", "exception", "asko_id")
