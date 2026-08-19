import pytest
from django.urls import reverse

from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicantFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from customer.tests.factories import CustomerFactory


@pytest.mark.django_db
def test_offer_message_falls_back_to_linked_application_applicant_email(
    elasticsearch, sales_ui_salesperson_api_client
):
    """
    - Uses linked application applicant email when profile email is empty.
    - Keeps recipient name from customer profile.
    """
    apartment = ApartmentDocumentFactory(
        apartment_number="A1",
        apartment_structure="2h+k",
        living_area=35.0,
        floor=2,
        sales_price=200000,
        debt_free_sales_price=250000,
        maintenance_fee=7000,
        project_ownership_type="hitas",
        project_housing_company="As Oy Esimerkki",
    )

    customer = CustomerFactory(primary_profile__email="")
    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="from-linked-application@example.com",
    )
    application_apartment = ApplicationApartmentFactory(
        application=application,
        apartment_uuid=apartment.uuid,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        application_apartment=application_apartment,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-offer-message",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["recipients"] == [
        {
            "name": customer.primary_profile.full_name,
            "email": "from-linked-application@example.com",
        }
    ]


@pytest.mark.django_db
def test_offer_message_falls_back_to_latest_applicant_when_no_linked_application(
    elasticsearch, sales_ui_salesperson_api_client
):
    """
    - Uses latest applicant email when profile email is empty.
    - Applies only when reservation has no linked application.
    """
    apartment = ApartmentDocumentFactory(
        apartment_number="A1",
        apartment_structure="2h+k",
        living_area=35.0,
        floor=2,
        sales_price=200000,
        debt_free_sales_price=250000,
        maintenance_fee=7000,
        project_ownership_type="hitas",
        project_housing_company="As Oy Esimerkki",
    )

    customer = CustomerFactory(primary_profile__email="")
    first_application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=first_application,
        is_primary_applicant=True,
        email="older@example.com",
    )
    latest_application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=latest_application,
        is_primary_applicant=True,
        email="latest@example.com",
    )

    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        application_apartment=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-offer-message",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["recipients"] == [
        {
            "name": customer.primary_profile.full_name,
            "email": "latest@example.com",
        }
    ]


@pytest.mark.django_db
def test_offer_message_keeps_email_empty_when_fallbacks_missing(
    elasticsearch, sales_ui_salesperson_api_client
):
    """
    - Keeps empty email when profile, linked application and latest applicant
      do not provide email.
    """
    apartment = ApartmentDocumentFactory(
        apartment_number="A1",
        apartment_structure="2h+k",
        living_area=35.0,
        floor=2,
        sales_price=200000,
        debt_free_sales_price=250000,
        maintenance_fee=7000,
        project_ownership_type="hitas",
        project_housing_company="As Oy Esimerkki",
    )

    customer = CustomerFactory(primary_profile__email="")
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        application_apartment=None,
    )

    response = sales_ui_salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-offer-message",
            kwargs={"pk": reservation.id},
        )
    )

    assert response.status_code == 200
    assert response.data["recipients"] == [
        {
            "name": customer.primary_profile.full_name,
            "email": "",
        }
    ]
