from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from users.models import Profile


def _create_token(profile: Profile) -> str:
    """Create a new, valid access token for the given profile."""
    return RefreshToken.for_user(profile.user).access_token


def _create_profile(profile_data: dict, password: str) -> Profile:
    """Create a new profile with the given data and user password."""
    data = profile_data.copy()
    user = get_user_model().objects.create(
        first_name=data.pop("first_name"),
        last_name=data.pop("last_name"),
        email=data.pop("email"),
    )
    user.set_password(password)
    user.save(update_fields=["password"])
    profile = Profile.objects.create(user=user, **data)
    profile.refresh_from_db()
    return profile
