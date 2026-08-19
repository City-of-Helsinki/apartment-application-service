import pytest

from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicantFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from customer.profile_resolver import (
    resolve_customer_profiles_for_customer,
    resolve_customer_profiles_for_reservation,
)
from customer.tests.factories import CustomerFactory


@pytest.mark.django_db
def test_resolver_prefers_profile_values_when_present():
    """
    - Uses profile values as primary source.
    - Does not override non-empty profile values.
    """
    customer = CustomerFactory(
        primary_profile__email="profile@example.com",
        primary_profile__phone_number="12345",
    )

    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="applicant@example.com",
        phone_number="99999",
    )

    primary, _secondary = resolve_customer_profiles_for_customer(customer)

    assert primary.email == "profile@example.com"
    assert primary.phone_number == "12345"


@pytest.mark.django_db
def test_resolver_uses_linked_application_when_profile_values_missing_or_dash():
    """
    - Treats empty and dash-like values as missing.
    - Uses linked reservation application applicant as fallback.
    """
    customer = CustomerFactory(
        primary_profile__email="-",
        primary_profile__phone_number=" ",
        primary_profile__street_address="-",
        primary_profile__postal_code="-",
        primary_profile__city="-",
    )
    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="linked@example.com",
        phone_number="0100200",
        street_address="Kekekatu 22",
        postal_code="00200",
        city="Helsinki",
    )
    application_apartment = ApplicationApartmentFactory(application=application)
    reservation = ApartmentReservationFactory(
        customer=customer,
        application_apartment=application_apartment,
    )

    primary, _secondary = resolve_customer_profiles_for_reservation(reservation)

    assert primary.email == "linked@example.com"
    assert primary.phone_number == "0100200"
    assert primary.street_address == "Kekekatu 22"
    assert primary.postal_code == "00200"
    assert primary.city == "Helsinki"


@pytest.mark.django_db
def test_resolver_uses_latest_application_when_no_linked_application():
    """
    - Uses latest application only when linked application does not exist.
    - Picks the newest application by created_at/id ordering.
    """
    customer = CustomerFactory(
        primary_profile__email="",
        primary_profile__phone_number="",
    )

    older = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=older,
        is_primary_applicant=True,
        email="older@example.com",
        phone_number="11111",
    )
    latest = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=latest,
        is_primary_applicant=True,
        email="latest@example.com",
        phone_number="22222",
    )

    reservation = ApartmentReservationFactory(
        customer=customer,
        application_apartment=None,
    )

    primary, _secondary = resolve_customer_profiles_for_reservation(reservation)

    assert primary.email == "latest@example.com"
    assert primary.phone_number == "22222"


@pytest.mark.django_db
def test_resolver_does_not_use_latest_when_linked_exists_but_lacks_values():
    """
    - Does not consult latest application when linked application exists.
    - Keeps missing value empty if linked applicant has no value.
    """
    customer = CustomerFactory(primary_profile__email="")

    linked_application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=linked_application,
        is_primary_applicant=True,
        email="",
    )
    application_apartment = ApplicationApartmentFactory(application=linked_application)

    latest_application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=latest_application,
        is_primary_applicant=True,
        email="latest@example.com",
    )

    reservation = ApartmentReservationFactory(
        customer=customer,
        application_apartment=application_apartment,
    )

    primary, _secondary = resolve_customer_profiles_for_reservation(reservation)

    assert primary.email == ""
