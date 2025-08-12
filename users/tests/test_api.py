from unittest.mock import patch
from uuid import UUID

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken

from audit_log.models import AuditLog
from users.enums import Roles
from users.masking import mask_string, mask_uuid, unmask_string, unmask_uuid
from users.models import Profile
from users.tests.conftest import (
    PROFILE_TEST_DATA,
    PROFILE_TEST_DATA_WITH_NIN,
    TEST_USER_PASSWORD,
)
from users.tests.factories import UserFactory
from users.tests.utils import _create_token

User = get_user_model()


@pytest.mark.django_db
def test_profile_get_list_is_not_allowed(profile, api_client):
    # Listing profiles should not be not allowed, since a user should
    # not be able to view anybody else's profiles.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(reverse("users:profile-list"))
    assert response.status_code == 405


@pytest.mark.django_db
def test_profile_get_detail(profile, api_client):
    # The user should be able to retrieve their own profile
    response = call_profile_get_detail(profile, api_client)
    check_profile_get_detail_response(response, profile, nin=None)


@pytest.mark.django_db
def test_profile_get_detail_with_nin(profile_with_nin, api_client):
    response = call_profile_get_detail(profile_with_nin, api_client)
    check_profile_get_detail_response(response, profile_with_nin, nin="250180-8887")


def call_profile_get_detail(profile, api_client):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
    )
    return response


def check_profile_get_detail_response(response, profile, nin):
    assert response.status_code == 200
    assert response.data == {
        **PROFILE_TEST_DATA,
        "is_salesperson": False,
        "national_identification_number": nin,
    }
    for attr, value in response.data.items():
        if hasattr(profile, attr):
            profile_value = getattr(profile, attr)
            if callable(profile_value):
                profile_value = profile_value()
            assert str(profile_value) == str(value)


@pytest.mark.django_db
def test_profile_get_detail_writes_audit_log(profile, api_client):
    # A successful "READ" entry should be left when the user views their own profile
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    api_client.get(reverse("users:profile-detail", args=(mask_uuid(profile.pk),)))
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "OWNER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "READ"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "SUCCESS"


@pytest.mark.django_db
def test_profile_get_detail_fails_if_not_own_profile(
    profile, other_profile, api_client
):
    # The user should not be able to view other users' profiles
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    response = api_client.get(
        reverse("users:profile-detail", args=(mask_uuid(other_profile.pk),))
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_profile_get_detail_writes_audit_log_if_not_own_profile(
    profile, other_profile, api_client
):
    # A forbidden "READ" entry should be left if the user
    # attemps to view someone else's profile.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    api_client.get(reverse("users:profile-detail", args=(mask_uuid(other_profile.pk),)))
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "USER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "READ"
    assert audit_event["target"] == {"id": str(other_profile.pk), "type": "Profile"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
def test_profile_get_detail_fails_if_not_authenticated(profile, api_client):
    # An unauthenticated user should not be able to view any profiles
    response = api_client.get(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_profile_get_detail_writes_audit_log_if_not_authenticated(profile, api_client):
    # A forbidden "READ" entry should be left if an unauthenticated user
    # tries to view somebody's profile.
    api_client.get(reverse("users:profile-detail", args=(mask_uuid(profile.pk),)))
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert audit_event["operation"] == "READ"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
@pytest.mark.parametrize("nin_kind", ["no NIN", "valid NIN", "invalid NIN"])
def test_profile_post(api_client, nin_kind):
    # Creating new profile should be allowed as an unauthenticated user
    if nin_kind == "no NIN":
        profile_data = PROFILE_TEST_DATA
    elif nin_kind == "valid NIN":
        profile_data = PROFILE_TEST_DATA_WITH_NIN
    elif nin_kind == "invalid NIN":
        # Note: Currently even invalid NINs are accepted
        profile_data = {
            **PROFILE_TEST_DATA_WITH_NIN,
            "national_identification_number": "123456-XXXX",
        }

    response = api_client.post(reverse("users:profile-list"), profile_data)
    assert response.status_code == 201
    user = User.objects.get()
    # Response should contain masked profile ID and password
    assert user.profile.pk == unmask_uuid(response.data["profile_id"])
    assert user.profile.pk == UUID(profile_data["id"])
    assert user.check_password(unmask_string(response.data["password"]))
    # We should be able to look up a profile based on the unmasked username
    profile = Profile.objects.get(pk=unmask_uuid(response.data["profile_id"]))
    # The created profile should contain all the data from the request
    for attr, value in profile_data.items():
        assert str(getattr(profile, attr)) == str(value)


@pytest.mark.django_db
def test_profile_post_non_ascii_characters_in_email_address(api_client):
    profile_data = PROFILE_TEST_DATA.copy()
    profile_data["email"] = "äåö@example.com"
    response = api_client.post(reverse("users:profile-list"), profile_data)
    assert response.status_code == 201, response.data
    user = User.objects.get()
    assert user.profile.email == "äåö@example.com"


@pytest.mark.django_db
def test_profile_post_writes_audit_log(api_client):
    api_client.post(reverse("users:profile-list"), PROFILE_TEST_DATA)
    profile = Profile.objects.get()
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert audit_event["operation"] == "CREATE"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "SUCCESS"


@pytest.mark.django_db
def test_salesperson_profile_post(api_client):
    # Set profile role
    profile_data = PROFILE_TEST_DATA.copy()
    profile_data["is_salesperson"] = True

    # Creating new profile should be allowed as an unauthenticated user
    response = api_client.post(reverse("users:profile-list"), profile_data)
    assert response.status_code == 201
    user = User.objects.get()
    # Response should contain masked profile ID and password
    assert user.profile.pk == unmask_uuid(response.data["profile_id"])
    assert user.profile.pk == UUID(profile_data["id"])
    assert user.check_password(unmask_string(response.data["password"]))
    # User should have a salesperson role
    assert user.groups.filter(name__iexact=Roles.DRUPAL_SALESPERSON.name).exists()
    # We should be able to look up a profile based on the unmasked username
    profile = Profile.objects.get(pk=unmask_uuid(response.data["profile_id"]))
    profile_data = profile_data.copy()
    # The created profile should contain all the data from the request
    for attr, value in profile_data.items():
        if hasattr(profile, attr):
            profile_value = getattr(profile, attr)
            if callable(profile_value):
                profile_value = profile_value()
            assert str(profile_value) == str(value)


@pytest.mark.django_db
def test_profile_put(profile, api_client):
    # A user should be able to update their own profile
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
    put_data = {
        **PROFILE_TEST_DATA,
        "first_name": "Maija",
        "street_address": "Kauppakatu 23",
    }
    response = api_client.put(url, put_data)
    assert response.status_code == 200
    profile.refresh_from_db()
    for attr, value in put_data.items():
        assert str(getattr(profile, attr)) == str(value)


@pytest.mark.django_db
def test_profile_put_writes_audit_log(profile, api_client):
    # A successful "UPDATE" entry should be left when the user updates their own profile
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    api_client.put(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),)),
        {**PROFILE_TEST_DATA, "first_name": "Maija", "address": "Kauppakatu 23"},
    )
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "OWNER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "UPDATE"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "SUCCESS"


@pytest.mark.django_db
def test_salesperson_profile_put(profile, api_client):
    # Set profile role
    profile_data = PROFILE_TEST_DATA.copy()
    profile_data["is_salesperson"] = True

    # A user should be able to update their own profile
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
    put_data = {
        **profile_data,
        "first_name": "Maija",
        "street_address": "Kauppakatu 23",
    }
    response = api_client.put(url, put_data)
    assert response.status_code == 200
    assert response.data == {
        **put_data,
        "national_identification_number": None,
    }
    profile.refresh_from_db()
    # User should have a salesperson role
    assert profile.user.groups.filter(
        name__iexact=Roles.DRUPAL_SALESPERSON.name
    ).exists()
    for attr, value in put_data.items():
        if hasattr(profile, attr):
            profile_value = getattr(profile, attr)
            if callable(profile_value):
                profile_value = profile_value()
            assert str(profile_value) == str(value)


@pytest.mark.django_db
def test_profile_put_fails_if_not_own_profile(profile, other_profile, api_client):
    # A user should not be able to update other users' profiles
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(other_profile.pk),))
    put_data = {
        **PROFILE_TEST_DATA,
        "first_name": "Maija",
        "street_address": "Kauppakatu 23",
    }
    response = api_client.put(url, put_data)
    assert response.status_code == 403


@pytest.mark.django_db
def test_profile_put_writes_audit_log_if_not_own_profile(
    profile, other_profile, api_client
):
    # A forbidden "UPDATE" event should be left if a user
    # tries to update another person's profile.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(other_profile.pk),))
    api_client.put(
        url,
        {**PROFILE_TEST_DATA, "first_name": "Maija", "street_address": "Kauppakatu 23"},
    )
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "USER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "UPDATE"
    assert audit_event["target"] == {"id": str(other_profile.pk), "type": "Profile"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
def test_profile_put_fails_if_not_authenticated(profile, api_client):
    # An unauthenticated user should not be able to update any profiles
    response = api_client.put(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),)),
        PROFILE_TEST_DATA,
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_profile_put_writes_audit_log_if_not_authenticated(profile, api_client):
    # A forbidden "UPDATE" entry should be written if an unauthenticated
    # user attempts to update a user's profile.
    api_client.put(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),)),
        PROFILE_TEST_DATA,
    )
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert audit_event["operation"] == "UPDATE"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
def test_profile_patch_is_not_allowed(profile, api_client):
    # Partial updates should not be allowed
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
    response = api_client.patch(
        url, {"first_name": "Maija", "street_address": "Kauppakatu 23"}
    )
    assert response.status_code == 405


@pytest.mark.django_db
def test_profile_delete(profile, api_client):
    # A user should be able to delete their own profile
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
    response = api_client.delete(url)
    assert response.status_code == 204
    assert not User.objects.filter(pk=profile.user.pk).exists()
    assert not Profile.objects.filter(pk=profile.pk).exists()


@pytest.mark.django_db
def test_profile_delete_writes_audit_log(profile, api_client):
    # A successful "DELETE" entry should be written if a user deletes their own profile
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    api_client.delete(reverse("users:profile-detail", args=(mask_uuid(profile.pk),)))
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "OWNER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "DELETE"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "SUCCESS"


@pytest.mark.django_db
def test_profile_delete_fails_if_not_own_profile(profile, other_profile, api_client):
    # A user should not be able to delete other users' profiles
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    url = reverse("users:profile-detail", args=(mask_uuid(other_profile.pk),))
    response = api_client.delete(url)
    assert response.status_code == 403


@pytest.mark.django_db
def test_profile_delete_writes_audit_log_if_not_own_profile(
    profile, other_profile, api_client
):
    # A forbidden "DELETE" entry should be written if a user
    # tries to delete another person's profile.
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    api_client.delete(
        reverse("users:profile-detail", args=(mask_uuid(other_profile.pk),))
    )
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "USER", "profile_id": str(profile.pk)}
    assert audit_event["operation"] == "DELETE"
    assert audit_event["target"] == {"id": str(other_profile.pk), "type": "Profile"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
def test_profile_delete_fails_if_not_authenticated(profile, api_client):
    # An unauthenticated user should not be able to delete any profiles
    response = api_client.delete(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),)),
        PROFILE_TEST_DATA,
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_profile_delete_writes_audit_log_if_not_authenticated(profile, api_client):
    # A forbidden "DELETE" event should be written if an unauthenticated user
    # tries to delete a user's profile.
    api_client.delete(
        reverse("users:profile-detail", args=(mask_uuid(profile.pk),)),
        PROFILE_TEST_DATA,
    )
    audit_event = AuditLog.objects.get().message["audit_event"]
    assert audit_event["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert audit_event["operation"] == "DELETE"
    assert audit_event["target"] == {"id": str(profile.pk), "type": "Profile"}
    assert audit_event["status"] == "FORBIDDEN"


@pytest.mark.django_db
@patch.object(Profile.objects, "create")
def test_profile_creation_is_rolled_back_on_profile_create_error(
    patched_profile_objects_create, api_client
):
    patched_profile_objects_create.side_effect = Exception
    with pytest.raises(Exception):
        api_client.post(reverse("users:profile-list"), PROFILE_TEST_DATA)
    assert not User.objects.filter(
        first_name=PROFILE_TEST_DATA["first_name"],
        last_name=PROFILE_TEST_DATA["last_name"],
        email=PROFILE_TEST_DATA["email"],
    ).exists()
    assert not Profile.objects.exists()


@pytest.mark.django_db
def test_profile_update_is_rolled_back_on_profile_save_error(profile, api_client):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    with patch.object(Profile, "save") as patched_profile_save:
        patched_profile_save.side_effect = Exception
        with pytest.raises(Exception):
            url = reverse("users:profile-detail", args=(mask_uuid(profile.pk),))
            put_data = {
                **PROFILE_TEST_DATA,
                "first_name": "Maija",
                "street_address": "Kauppakatu 23",
            }
            api_client.put(url, put_data)
    profile.refresh_from_db()
    assert profile.first_name == PROFILE_TEST_DATA["first_name"]
    assert profile.street_address == PROFILE_TEST_DATA["street_address"]


@pytest.mark.django_db
def test_token(profile, api_client):
    # The user should receive refresh and access tokens
    # when logging in with valid credentials.
    credentials = {
        "profile_id": mask_uuid(profile.pk),
        "password": mask_string(TEST_USER_PASSWORD),
    }
    response = api_client.post(reverse("token_obtain_pair"), credentials)
    assert response.status_code == 200
    assert "refresh" in response.data
    assert "access" in response.data


@pytest.mark.django_db
def test_token_fails_if_credentials_are_invalid(profile, api_client):
    # The user should not receive any tokens if the credentials are invalid
    credentials = {
        "profile_id": mask_uuid(profile.pk),
        "password": mask_string("wrong password"),
    }
    response = api_client.post(reverse("token_obtain_pair"), credentials)
    assert response.status_code == 401


@pytest.mark.django_db
def test_token_refresh(profile, api_client):
    # The user should receive an access token, given a valid refresh token
    refresh_token = RefreshToken.for_user(profile.user)
    post_data = {"refresh": str(refresh_token)}
    response = api_client.post(reverse("token_refresh"), post_data)
    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_salesperson_list_not_authorized(user_api_client):
    """Only salespersons should be able to list salespersons"""
    response = user_api_client.get(reverse("v1/profiles:user-list"))
    assert response.status_code == 403


@pytest.mark.django_db
def test_salesperson_list_only_contains_salespersons(sales_ui_salesperson_api_client):
    # create some users, 5 regular users, 5 salespeople
    user_count = 10
    salesperson_count = 5
    salesperson_group = Group.objects.get(name__iexact=Roles.DJANGO_SALESPERSON.name)
    regular_user_uuids = []
    salesperson_uuids = []

    for idx in range(user_count):
        user = UserFactory()
        if idx >= 5:
            salesperson_group.user_set.add(user)
            salesperson_uuids.append(user.uuid)
        else:
            regular_user_uuids.append(user.uuid)

    response = sales_ui_salesperson_api_client.get(reverse("v1/profiles:user-list"))
    response_uuids = [user["uuid"] for user in response.json()]

    # none of the regular users are in salesperson list
    assert (
        len(
            [
                user_uuid
                for user_uuid in regular_user_uuids
                if user_uuid in response_uuids
            ]
        )
        == 0
    )

    # all of the salespeople are in salesperson list
    assert (
        len(
            [
                user_uuid
                for user_uuid in salesperson_uuids
                if user_uuid in salesperson_uuids
            ]
        )
        == salesperson_count
    )
