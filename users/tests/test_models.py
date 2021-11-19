import pytest

from users.models import Profile
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_profile_exist_after_user_is_deleted():
    profile = ProfileFactory()

    profile.user.delete()

    assert Profile.objects.all().count() == 1
    assert Profile.objects.first().user is None
