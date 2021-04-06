import random
from django.db.models import QuerySet
from django.utils.translation import ugettext_lazy as _
from simple_history.utils import bulk_update_with_history
from typing import List, Optional, Union

from application_form.models import (
    Apartment,
    ApplicationMixin,
    HasoApartmentPriority,
    HasoApplication,
    HitasApplication,
)
from application_form.selectors import (
    get_apartment_hitas_application_queue,
    get_haso_apartments,
    get_winning_haso_apartment_priorities_by_apartment,
    get_winning_haso_apartment_priorities_for_application,
    list_hitas_apartments,
)

# HASO


def deactivate_haso_apartment_priorities(
    application: HasoApplication, apartment: Apartment
) -> None:
    """
    Deactivate all the other Haso apartment priorities when the applicant has
    accepted an offer.
    """
    haso_apartment_priorities = HasoApartmentPriority.objects.filter(
        haso_application=application
    ).exclude(apartment=apartment)
    for haso_apartment_priority in haso_apartment_priorities:
        haso_apartment_priority.is_active = False
        haso_apartment_priority._change_reason = _(
            "haso application deactivated due to accepted offer."
        )
    bulk_update_with_history(
        haso_apartment_priorities, HasoApartmentPriority, ["is_active"]
    )


def create_or_update_apartments_and_priorities(
    apartment_uuids: List[str], haso_application: HasoApplication
) -> None:
    """
    Create Haso apartment priorities for each apartment uuid provided.
    Get or create an apartment for each apartment uuid.
    """
    # Here we assume that the apartment_uuids list is already in the
    # prioritized order.
    for idx, apartment_uuid in enumerate(apartment_uuids):
        apartment = get_or_create_apartment_with_uuid(apartment_uuid)
        HasoApartmentPriority.objects.get_or_create(
            priority_number=idx,
            apartment=apartment,
            haso_application=haso_application,
        )


def check_first_place_haso_applications(
    haso_applications: Optional[QuerySet] = None, apartments: Optional[QuerySet] = None
) -> None:
    """
    If there are multiple 1st place haso apartment priorities, we need to deactivate
    the lowest priorities.
    """
    if not haso_applications:
        haso_applications = HasoApplication.objects.approved()

    if not apartments:
        apartments = get_haso_apartments()

    priorities_updated = True
    # Run as long as there are priorities updated. This is to check that
    # by deactivating one priority, it won't cause new duplicate 1st place priorities.
    while priorities_updated:
        winning_apartment_priorities = (
            get_winning_haso_apartment_priorities_by_apartment(apartments)
        )

        priorities_updated = False
        for haso_application in haso_applications:
            # Get all the 1st place priorities in the current application.
            # Slice off the lowest `priority_number`.
            application_priority_queryset = (
                get_winning_haso_apartment_priorities_for_application(
                    haso_application, winning_apartment_priorities
                )[1:]
            )

            # Deactivate all but the first priority.
            for application_priority in application_priority_queryset:
                application_priority.is_active = False
                application_priority._change_reason = _(
                    "priority deactivated due to application being "
                    "first place in multiple apartment queues."
                )
                priorities_updated = True

            if priorities_updated:
                bulk_update_with_history(
                    application_priority_queryset,
                    HasoApartmentPriority,
                    ["is_active"],
                )


# HITAS


def shuffle_hitas_applications(hitas_applications: QuerySet) -> None:
    """
    Shuffle hitas applications so that applications with children come first.
    """
    # Divide the applications according to the `has_children` boolean value.
    applications_with_children = list(hitas_applications.filter(has_children=True))
    applications_without_children = list(hitas_applications.filter(has_children=False))

    # Shuffle the two lists separately.
    random.shuffle(applications_with_children)
    random.shuffle(applications_without_children)

    # Finally combine the lists so that the applications with children come first
    # and set the order for them respectively.
    hitas_application_list = applications_with_children + applications_without_children
    for i, hitas_application in enumerate(hitas_application_list):
        # The order is visible to the user.
        # To avoid confusion, we start the ordering from 1.
        hitas_application.order = i + 1
        hitas_application._change_reason = _("hitas applications shuffled.")
        hitas_application.save()


def shuffle_hitas_applications_by_apartments(
    apartments: Optional[QuerySet] = None,
) -> None:
    """
    Shuffle hitas applications of each apartment separately.
    """
    if not apartments:
        apartments = list_hitas_apartments()
    for apartment in apartments:
        hitas_applications = get_apartment_hitas_application_queue(apartment)
        shuffle_hitas_applications(hitas_applications)


# GENERAL


def accept_offer(
    application: Union[ApplicationMixin, HasoApplication, HitasApplication],
    apartment: Apartment,
) -> None:
    """
    Handles the logic when an applicant accepts the offered apartment.
    """
    application.applicant_has_accepted_offer = True
    application._change_reason = _("applicant has accepted an offer.")
    application.save()
    if isinstance(application, HasoApplication):
        deactivate_haso_apartment_priorities(application, apartment)

    apartment.is_available = False
    apartment._change_reason = _("apartment offer accepted by an applicant.")
    apartment.save()


def get_or_create_apartment_with_uuid(apartment_uuid: str) -> Apartment:
    """
    Gets or creates an apartment with the provided uuid string.
    """
    apartment, _ = Apartment.objects.get_or_create(
        apartment_uuid=apartment_uuid,
    )
    return apartment
