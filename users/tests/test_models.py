import pytest
from django.core.exceptions import ValidationError

from users.models import Profile
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_profile_exist_after_user_is_deleted():
    profile = ProfileFactory()

    profile.user.delete()

    assert Profile.objects.all().count() == 1
    assert Profile.objects.first().user is None


@pytest.mark.django_db
def test_profile_national_identification_number_validation():
    profile = ProfileFactory()

    # Invalid format
    profile.national_identification_number = "123456-1234"
    with pytest.raises(ValidationError, match="The number has an invalid format."):
        profile.clean()

    # Invalid checksum
    profile.national_identification_number = "131052-308U"
    with pytest.raises(
        ValidationError, match="The number's checksum or check digit is invalid."
    ):
        profile.clean()

    # Correct checksum
    profile.national_identification_number = "131052-308T"
    profile.save()
