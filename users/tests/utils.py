from datetime import date
from typing import Optional
from uuid import UUID

from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

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


def assert_customer_match_data(customer: Customer, data: dict, compact: bool = False):
    if "primary_profile" in data:
        assert_profile_match_data(
            customer.primary_profile, data["primary_profile"], compact=compact
        )
    if "secondary_profile" in data:
        assert_profile_match_data(
            customer.secondary_profile, data["secondary_profile"], compact=compact
        )

    fields = ("id",)
    if not compact:
        fields += (
            "additional_information",
            "last_contact_date",
            "has_children",
            "has_hitas_ownership",
            "is_age_over_55",
            "is_right_of_occupancy_housing_changer",
            "right_of_residence",
            "right_of_residence_is_old_batch",
        )
    assert_obj_match_data(customer, data, fields)


def assert_profile_match_data(
    profile: Optional[Profile], data: Optional[dict], compact: bool = False
):
    if not data:
        assert profile is None
        return

    fields = (
        "id",
        "first_name",
        "last_name",
    )

    if not compact:
        fields += (
            "email",
            "phone_number",
            "street_address",
            "city",
            "postal_code",
            "contact_language",
            "national_identification_number",
            "date_of_birth",
        )
    assert_obj_match_data(profile, data, fields)


def assert_obj_match_data(obj, data, fields):
    for field in fields:
        if field in data:
            obj_value = getattr(obj, field)
            if isinstance(obj_value, date) or isinstance(obj_value, UUID):
                obj_value = str(obj_value)
            assert data[field] == obj_value, f"{field}: {data[field]} != {obj_value}"
