from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        "primary_profile",
        "secondary_profile",
        "additional_information",
        "last_contact_date",
        "created_at",
        "updated_at",
    )
