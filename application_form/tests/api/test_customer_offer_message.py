import pytest
from django.urls import reverse

from apartment.models import ProjectExtraData
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.tests.api.test_customer_offer_update import (
    _create_offered_reservation,
    _customer_client,
)
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_customer_offer_message_returns_email_body(api_client):
    """
    - Customer can fetch offer message subject and body for their own offer.
    """
    profile = ProfileFactory()
    apartment = ApartmentDocumentFactory(
        apartment_number="A1",
        project_housing_company="As Oy Testitalo",
    )
    ProjectExtraData.objects.create(
        project_uuid=apartment.project_uuid,
        offer_message_intro="Intro text",
        offer_message_content="Footer text",
    )
    _, offer = _create_offered_reservation(profile, apartment=apartment)
    client = _customer_client(profile)

    response = client.get(
        reverse(
            "application_form:customer_offer_message",
            kwargs={"offer_id": offer.id},
        ),
    )

    assert response.status_code == 200
    assert response.data["subject"] == "Tarjous As Oy Testitalo A1"
    assert "Intro text" in response.data["body"]
    assert "Huoneisto: A1" in response.data["body"]
    assert "Footer text" in response.data["body"]


@pytest.mark.django_db
def test_customer_offer_message_other_profile_returns_404(api_client):
    """
    - Customer cannot fetch offer message for another profile's offer.
    """
    owner = ProfileFactory()
    other = ProfileFactory()
    _, offer = _create_offered_reservation(owner)

    response = _customer_client(other).get(
        reverse(
            "application_form:customer_offer_message",
            kwargs={"offer_id": offer.id},
        ),
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_customer_offer_message_unauthorized(api_client):
    """
    - Unauthenticated request is rejected.
    """
    profile = ProfileFactory()
    _, offer = _create_offered_reservation(profile)

    response = api_client.get(
        reverse(
            "application_form:customer_offer_message",
            kwargs={"offer_id": offer.id},
        ),
    )

    assert response.status_code == 401
