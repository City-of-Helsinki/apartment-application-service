from django.contrib import admin

from cost_index.models import CostIndex


@admin.register(CostIndex)
class CostIndexAdmin(admin.ModelAdmin):
    list_display = ["admin_valid_from", "value"]

    @admin.display(description="Valid from")
    def admin_valid_from(self, obj):
        return obj.valid_from.strftime("%d.%m.%Y")
