import pytest
from django.urls import reverse

from application_form.tests.api.test_customer_offer_update import (
    _create_offered_reservation,
    _customer_client,
)
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_customer_offer_details_returns_structured_items(api_client):
    """
    Test that authenticated customer can fetch structured offer details.

    - returns `subject`
    - returns ordered `items` list of key/value pairs (email dynamic part)
    """
    profile = ProfileFactory()
    reservation, offer = _create_offered_reservation(profile=profile)
    reservation.has_children = True
    reservation.save(update_fields=["has_children"])

    client = _customer_client(profile)
    url = reverse("application_form:customer_offer_details", kwargs={"offer_id": offer.id})
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert "subject" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    assert any(item["key"] == "apartment_number" for item in data["items"])
    assert any(
        item["key"] in ("has_children", "right_of_residence") for item in data["items"]
    )
    assert any(item["key"] == "valid_until" for item in data["items"])


@pytest.mark.django_db
def test_customer_offer_details_other_profile_returns_404(api_client):
    """
    Test that customer cannot access another customer's offer details.
    """
    profile = ProfileFactory()
    _reservation, offer = _create_offered_reservation(profile=profile)

    other_profile = ProfileFactory()
    client = _customer_client(other_profile)
    url = reverse("application_form:customer_offer_details", kwargs={"offer_id": offer.id})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_customer_offer_details_unauthorized(api_client):
    """
    Test that unauthenticated user cannot fetch offer details.
    """
    profile = ProfileFactory()
    _reservation, offer = _create_offered_reservation(profile=profile)

    url = reverse("application_form:customer_offer_details", kwargs={"offer_id": offer.id})
    response = api_client.get(url)

    assert response.status_code == 401

