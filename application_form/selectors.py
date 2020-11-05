from django.db.models import OuterRef, QuerySet, Subquery

from application_form.models import (
    Apartment,
    HasoApartmentPriority,
    HasoApplication,
    HitasApplication,
)

# HASO


def list_haso_applications() -> QuerySet:
    """
    Get all HasoApplications
    """
    return HasoApplication.objects.all()


def get_apartment_haso_application_id_queue(apartment: Apartment) -> list:
    """
    For the given apartment, return a list of Haso right_of_occupancy_ids
    ordered by the right_of_occupancy_id.
    """
    return list(
        HasoApartmentPriority.objects.filter(
            is_active=True,
            apartment=apartment,
        )
        .order_by("haso_application__right_of_occupancy_id")
        .values_list("haso_application__right_of_occupancy_id", flat=True)
    )


def get_haso_apartment_uuids(haso_application: HasoApplication) -> list:
    """
    From the given Haso application, get all apartment uuids
    ordered by the priority of the apartment.
    """
    return list(
        HasoApartmentPriority.objects.filter(haso_application=haso_application)
        .order_by("priority_number")
        .values_list("apartment__apartment_uuid", flat=True)
    )


def get_haso_apartments() -> QuerySet:
    """
    Get all apartments that are linked to Haso applications.
    """
    return Apartment.objects.filter(
        is_available=True, haso_apartment_priorities__isnull=False
    )


def get_winning_haso_apartment_priorities_by_apartment(
    apartments: QuerySet,
) -> QuerySet:
    """
    Returns a list of the winning haso apartment priorities for each given apartment.
    """
    ordered_priorities = HasoApartmentPriority.objects.filter(
        is_active=True, apartment=OuterRef("pk")
    ).order_by("haso_application__right_of_occupancy_id")

    # List of the winning haso apartment priorities for each apartment.
    return apartments.annotate(
        best_priority=Subquery(ordered_priorities.values("pk")[:1])
    ).values("best_priority")


def get_winning_haso_apartment_priorities_for_application(
    haso_application: HasoApplication, winning_apartment_priorities: QuerySet
) -> QuerySet:
    """
    Returns all the 1st place priorities in the provided application
    ordered by the apartment priorities in the application.
    """
    return HasoApartmentPriority.objects.filter(
        haso_application=haso_application,
        pk__in=winning_apartment_priorities,
    ).order_by("priority_number")


# HITAS


def list_hitas_applications():
    """
    Returns all Hitas applications.
    """
    return HitasApplication.objects.all()


def list_hitas_apartments():
    """
    Returns all apartments that are linked to Hitas applications.
    """
    return Apartment.objects.filter(is_available=True, hitas_applications__isnull=False)


def get_apartment_hitas_application_queue(apartment: Apartment) -> QuerySet:
    """
    For the given apartment, return a queryset of Hitas applications
    ordered by the ordering number.
    """
    return HitasApplication.objects.filter(
        apartment=apartment,
    ).order_by("order")
