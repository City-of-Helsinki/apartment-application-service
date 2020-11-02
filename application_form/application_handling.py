from django.db.models import OuterRef, QuerySet, Subquery
from typing import Optional

from application_form.models import Apartment, HasoApartmentPriority, HasoApplication


def deactivate_haso_apartment_priorities(
    haso_applications: Optional[QuerySet] = None, apartments: Optional[QuerySet] = None
):
    """
    If there are multiple 1st place haso apartment priorities, we need to deactivate
    the lowest priorities.
    """
    if not haso_applications:
        haso_applications = HasoApplication.objects.approved()

    if not apartments:
        apartments = Apartment.objects.filter(is_available=True)

    priorities_updated = True
    # Run as long as there are priorities updated. This is to check that
    # by deactivating one priority, it won't cause new duplicate 1st place priorities.
    while priorities_updated:
        ordered_priorities = HasoApartmentPriority.objects.filter(
            is_active=True, apartment=OuterRef("pk")
        ).order_by("haso_application__right_of_occupancy_id")

        # List of the winning haso apartment priorities for each apartment.
        winning_apartment_priority_pks = apartments.annotate(
            best_priority=Subquery(ordered_priorities.values("pk")[:1])
        ).values("best_priority")

        priorities_updated = False
        for haso_application in haso_applications:
            # All the 1st place priorities in the current application
            # ordered by the apartment priorities in the applicaiton.
            application_priority_queryset = HasoApartmentPriority.objects.filter(
                haso_application=haso_application,
                pk__in=winning_apartment_priority_pks,
            ).order_by("priority_number")

            # Deactivate all but the first priority.
            num_priorities_updated = application_priority_queryset.exclude(
                pk=application_priority_queryset[:1]
            ).update(is_active=False)

            # If an apartment was deactivated, we need to run this loop again
            # to check if there are new duplicate 1st places.
            if num_priorities_updated > 0:
                priorities_updated = True
