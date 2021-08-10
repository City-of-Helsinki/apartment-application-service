import json
from django.contrib import admin
from django.utils.safestring import mark_safe
from pygments import highlight
from pygments.formatters.html import HtmlFormatter
from pygments.lexers.data import JsonLexer

from audit_log.models import AuditLog
from audit_log.paginators import LargeTablePaginator


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    exclude = ("message",)
    readonly_fields = ("message_prettified",)

    # For increasing listing performance
    show_full_result_count = False
    paginator = LargeTablePaginator

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def message_prettified(self, instance):
        """Format the message to be a bit a more user-friendly."""
        message = json.dumps(instance.message, indent=2, sort_keys=True)
        formatter = HtmlFormatter()
        formatted_message = highlight(message, JsonLexer(), formatter)
        content = f"<style>{formatter.get_style_defs()}</style>{formatted_message}"
        return mark_safe(content)

    message_prettified.short_description = "message"
