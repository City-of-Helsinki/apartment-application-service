from django.contrib import admin

from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
    ApplicationApartment,
    Offer,
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


class ApartmentReservationStateChangeEventInline(admin.TabularInline):
    model = ApartmentReservationStateChangeEvent
    readonly_fields = ("timestamp", "state", "user", "comment")
    fk_name = "reservation"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class OfferInline(admin.TabularInline):
    model = Offer
    extra = 0


@admin.register(ApartmentReservation)
class ApartmentReservationAdmin(admin.ModelAdmin):
    inlines = [OfferInline, ApartmentReservationStateChangeEventInline]
