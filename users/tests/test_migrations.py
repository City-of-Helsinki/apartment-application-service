from datetime import date

import pgcrypto.fields
import pytest
from django.db import models
from django.db.models import Model
from faker import Faker


@pytest.mark.django_db
def test_0021_decrypt_profile(migrator):
    faker = Faker()

    old_state = migrator.apply_initial_migration(
        ("users", "0020_djangouser_drupaluser")
    )
    OldProfile: Model = old_state.apps.get_model("users", "Profile")

    def get_test_data():
        return {
            "calling_name": faker.first_name(),
            "city": faker.city(),
            "contact_language": faker.country_code(),
            "email": faker.email(),
            "first_name": faker.first_name(),
            "middle_name": faker.first_name(),
            "last_name": faker.last_name(),
            "phone_number": faker.phone_number(),
            "phone_number_nightly": None,
            "postal_code": str(faker.random_number(digits=5, fix_len=True)),
            "street_address": faker.address(),
        }

    encrypted_field_map = {
        "calling_name": pgcrypto.fields.CharPGPPublicKeyField,
        "city": pgcrypto.fields.CharPGPPublicKeyField,
        "contact_language": pgcrypto.fields.CharPGPPublicKeyField,
        "email": pgcrypto.fields.CharPGPPublicKeyField,
        "first_name": pgcrypto.fields.CharPGPPublicKeyField,
        "middle_name": pgcrypto.fields.CharPGPPublicKeyField,
        "last_name": pgcrypto.fields.CharPGPPublicKeyField,
        "phone_number": pgcrypto.fields.CharPGPPublicKeyField,
        "phone_number_nightly": pgcrypto.fields.CharPGPPublicKeyField,
        "postal_code": pgcrypto.fields.CharPGPPublicKeyField,
        "street_address": pgcrypto.fields.CharPGPPublicKeyField,
    }

    decrypted_field_map = {
        "calling_name": models.CharField,
        "city": models.CharField,
        "contact_language": models.CharField,
        "email": models.CharField,
        "first_name": models.CharField,
        "middle_name": models.CharField,
        "last_name": models.CharField,
        "phone_number": models.CharField,
        "phone_number_nightly": models.CharField,
        "postal_code": models.CharField,
        "street_address": models.CharField,
    }

    profile_1_test_data = get_test_data()
    profile_2_test_data = get_test_data()

    profile_1 = OldProfile.objects.create(
        date_of_birth=date.today(), **profile_1_test_data
    )
    profile_2 = OldProfile.objects.create(
        date_of_birth=date.today(), **profile_2_test_data
    )

    # Verify forward migrate

    new_state = migrator.apply_tested_migration(("users", "0021_decrypt_profile"))

    NewProfile: Model = new_state.apps.get_model("users", "Profile")

    def assert_field_type(model, field_name, expected_type):
        assert (field_name, type(model._meta.get_field(field_name))) == (
            field_name,
            expected_type,
        )

    for k, v in decrypted_field_map.items():
        assert_field_type(NewProfile, k, v)

    assert NewProfile.objects.all().count() == 2
    profile_1 = NewProfile.objects.get(pk=profile_1.pk)
    profile_2 = NewProfile.objects.get(pk=profile_2.pk)

    for k, v in profile_1_test_data.items():
        assert getattr(profile_1, k) == v

    for k, v in profile_2_test_data.items():
        assert getattr(profile_2, k) == v

    # Verify backward migrate

    reverted_state = migrator.apply_tested_migration(
        ("users", "0020_djangouser_drupaluser")
    )

    RevertedProfile: Model = reverted_state.apps.get_model("users", "Profile")

    for k, v in encrypted_field_map.items():
        assert_field_type(RevertedProfile, k, v)

    assert RevertedProfile.objects.all().count() == 2
    profile_1 = RevertedProfile.objects.get(pk=profile_1.pk)
    profile_2 = RevertedProfile.objects.get(pk=profile_2.pk)

    for k, v in profile_1_test_data.items():
        assert getattr(profile_1, k) == v

    for k, v in profile_2_test_data.items():
        assert getattr(profile_2, k) == v
