import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from unittest.mock import patch

from users.models import Profile

User = get_user_model()

PROFILE_TEST_DATA = {
    "id": "c4dcda4a-72b8-48ca-add0-0a17ec05ec0b",
    "first_name": "Mikko",
    "last_name": "Mallikas",
    "email": "example@example.com",
    "phone_number": "+358123456789",
    "address": "Mannerheiminkatu 3",
    "city": "Helsinki",
    "postal_code": "00100",
    "date_of_birth": "1980-01-25",
    "right_of_residence": "123456789",
    "contact_language": "fi",
}


@pytest.fixture
def profile():
    data = PROFILE_TEST_DATA.copy()
    user = User.objects.create(
        first_name=data.pop("first_name"),
        last_name=data.pop("last_name"),
        email=data.pop("email"),
    )
    return Profile.objects.create(user=user, **data)


@pytest.mark.django_db
def test_profile_get_list(profile):
    response = APIClient().get(reverse("v1/profiles:profile-list"))
    assert response.status_code == 200
    assert response.data == [PROFILE_TEST_DATA]


@pytest.mark.django_db
def test_profile_get_detail(profile):
    response = APIClient().get(
        reverse("v1/profiles:profile-detail", args=(PROFILE_TEST_DATA["id"],))
    )
    assert response.status_code == 200
    assert response.data == PROFILE_TEST_DATA


@pytest.mark.django_db
def test_profile_post():
    response = APIClient().post(reverse("v1/profiles:profile-list"), PROFILE_TEST_DATA)
    assert response.status_code == 201
    assert response.data == PROFILE_TEST_DATA
    profile = Profile.objects.get(pk=PROFILE_TEST_DATA["id"])
    profile_data = PROFILE_TEST_DATA.copy()
    for attr in ["first_name", "last_name", "email"]:
        assert str(getattr(profile.user, attr)) == str(profile_data.pop(attr))
    for attr, value in profile_data.items():
        assert str(getattr(profile, attr)) == str(value)


@pytest.mark.django_db
def test_profile_put(profile):
    url = reverse("v1/profiles:profile-detail", args=(PROFILE_TEST_DATA["id"],))
    put_data = {**PROFILE_TEST_DATA, "first_name": "Maija", "address": "Kauppakatu 23"}
    response = APIClient().put(url, put_data)
    assert response.status_code == 200
    assert response.data == put_data
    profile.refresh_from_db()
    for attr in ["first_name", "last_name", "email"]:
        assert str(getattr(profile.user, attr)) == str(put_data.pop(attr))
    for attr, value in put_data.items():
        assert str(getattr(profile, attr)) == str(value)


@pytest.mark.django_db
def test_profile_patch(profile):
    url = reverse("v1/profiles:profile-detail", args=(PROFILE_TEST_DATA["id"],))
    patch_data = {"first_name": "Maija", "address": "Kauppakatu 23"}
    response = APIClient().patch(url, patch_data)
    assert response.status_code == 200
    assert response.data == {**PROFILE_TEST_DATA, **patch_data}
    profile.refresh_from_db()
    assert profile.address == patch_data["address"]
    assert profile.user.first_name == patch_data["first_name"]


@pytest.mark.django_db
def test_profile_delete(profile):
    url = reverse("v1/profiles:profile-detail", args=(PROFILE_TEST_DATA["id"],))
    response = APIClient().delete(url)
    assert response.status_code == 204
    assert not User.objects.filter(pk=profile.user.pk).exists()
    assert not Profile.objects.filter(pk=profile.pk).exists()


@pytest.mark.django_db
@patch.object(Profile.objects, "create")
def test_profile_creation_is_rolled_back_on_profile_create_error(
    patched_profile_objects_create,
):
    patched_profile_objects_create.side_effect = Exception
    with pytest.raises(Exception):
        APIClient().post(reverse("v1/profiles:profile-list"), PROFILE_TEST_DATA)
    assert not User.objects.filter(
        first_name=PROFILE_TEST_DATA["first_name"],
        last_name=PROFILE_TEST_DATA["last_name"],
        email=PROFILE_TEST_DATA["email"],
    ).exists()
    assert not Profile.objects.filter(pk=PROFILE_TEST_DATA["id"]).exists()


@pytest.mark.django_db
def test_profile_update_is_rolled_back_on_profile_save_error(profile):
    with patch.object(Profile, "save") as patched_profile_save:
        patched_profile_save.side_effect = Exception
        with pytest.raises(Exception):
            url = reverse("v1/profiles:profile-detail", args=(PROFILE_TEST_DATA["id"],))
            put_data = {
                **PROFILE_TEST_DATA,
                "first_name": "Maija",
                "address": "Kauppakatu 23",
            }
            APIClient().put(url, put_data)
    profile.refresh_from_db()
    assert profile.user.first_name == PROFILE_TEST_DATA["first_name"]
    assert profile.address == PROFILE_TEST_DATA["address"]
