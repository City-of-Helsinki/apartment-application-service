from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date
from rest_framework_simplejwt.tokens import RefreshToken
from typing import Optional

from customer.models import Customer
from users.models import Profile


def _create_token(profile: Profile) -> str:
    """Create a new, valid access token for the given profile."""
    return RefreshToken.for_user(profile.user).access_token


def _create_profile(profile_data: dict, password: str) -> Profile:
    """Create a new profile with the given data and user password."""
    data = profile_data.copy()
    user = get_user_model().objects.create()
    user.set_password(password)
    user.save(update_fields=["password"])
    profile = Profile.objects.create(user=user, **data)
    profile.refresh_from_db()
    return profile


def assert_customer_match_data(customer: Customer, data: dict):
    if "primary_profile" in data:
        assert_profile_match_data(customer.primary_profile, data["primary_profile"])
    if "secondary_profile" in data:
        assert_profile_match_data(customer.secondary_profile, data["secondary_profile"])

    fields = (
        "additional_information",
        "last_contact_date",
        "has_children",
        "has_hitas_ownership",
        "is_age_over_55",
        "is_right_of_occupancy_housing_changer",
        "right_of_residence",
    )
    assert_obj_match_data(customer, data, fields)


def assert_profile_match_data(profile: Optional[Profile], data: Optional[dict]):
    if not data:
        assert profile is None
        return

    for field in (
        "id",
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "street_address",
        "city",
        "postal_code",
        "contact_language",
        "national_identification_number",
    ):
        if field in data:
            assert data[field] == getattr(
                profile, field
            ), f"{field} {data[field]} != {str(getattr(profile, field))}"

    if "date_of_birth" in data:
        assert parse_date(data["date_of_birth"]) == profile.date_of_birth


def assert_obj_match_data(obj, data, fields):
    for field in fields:
        if field in data:
            assert data[field] == getattr(
                obj, field
            ), f"{field}: {data[field]} != {getattr(obj, field)}"
