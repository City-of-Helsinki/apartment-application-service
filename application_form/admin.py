from django.contrib import admin

from application_form.models import (
    ApartmentReservation,
    Applicant,
    Application,
    ApplicationApartment,
)


@admin.register(Applicant)
class ApplicantAdmin(admin.ModelAdmin):
    pass


class ApplicationApartmentInline(admin.TabularInline):
    model = ApplicationApartment
    extra = 0


class ApplicantInline(admin.TabularInline):
    model = Applicant
    extra = 0


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    inlines = [ApplicantInline, ApplicationApartmentInline]


@admin.register(ApartmentReservation)
class ApartmentReservationAdmin(admin.ModelAdmin):
    pass
