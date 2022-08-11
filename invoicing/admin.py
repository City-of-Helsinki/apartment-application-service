from django.contrib import admin

from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate


@admin.register(ProjectInstallmentTemplate)
class ProjectInstallmentTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "type",
        "value",
        "unit",
        "percentage_specifier",
        "account_number",
        "due_date",
        "project_uuid",
    )


@admin.register(ApartmentInstallment)
class ApartmentInstallmentAdmin(admin.ModelAdmin):
    list_display = (
        "type",
        "value",
        "account_number",
        "due_date",
        "reference_number",
        "apartment_reservation",
    )
