import factory
import pytest

from application_form.application_handling import deactivate_haso_apartment_priorities
from application_form.models import HasoApplication
from application_form.tests.factories import (
    ApartmentFactory,
    HasoApartmentPriorityFactory,
    HasoApplicationFactory,
)


@pytest.mark.django_db
def test_haso_application_deactivation():
    apartments = ApartmentFactory.create_batch(5)
    for i in range(5):
        haso_application = HasoApplicationFactory(
            right_of_occupancy_id=i, is_approved=True, haso_apartment_priorities=None
        )
        HasoApartmentPriorityFactory.create_batch(
            5, haso_application=haso_application, apartment=factory.Iterator(apartments)
        )

    deactivate_haso_apartment_priorities()

    # With 5 applications for the same 5 apartments, the applications should have
    # 1, 2, 3, 4, 5 active apartment priorities respectively.
    for i, haso_application in enumerate(
        HasoApplication.objects.all().order_by("right_of_occupancy_id")
    ):
        assert (
            haso_application.haso_apartment_priorities.filter(is_active=True).count()
            == i + 1
        )
