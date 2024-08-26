from datetime import date

import pgcrypto.fields
import pytest
from django.db import models
from django.db.models import Model
from django.utils import dateparse
from faker import Faker
from pgcrypto.fields import IntegerPGPPublicKeyField

from apartment_application_service.fields import BooleanPGPPublicKeyField


@pytest.mark.django_db
def test_0007_and_0008_decrypt(migrator):
    faker = Faker()

    old_state = migrator.apply_initial_migration(
        ("customer", "0005_add_right_of_residence_is_old_batch")
    )
    OldProfile: Model = old_state.apps.get_model("users", "Profile")
    OldCustomer: Model = old_state.apps.get_model("customer", "Customer")

    profile_1 = OldProfile.objects.create(date_of_birth=date.today())
    profile_2 = OldProfile.objects.create(date_of_birth=date.today())

    def get_test_data():
        return {
            "is_right_of_occupancy_housing_changer": faker.boolean(),
            "has_hitas_ownership": faker.boolean(),
            "right_of_residence": faker.random_int(min=1, max=100000),
            "right_of_residence_is_old_batch": faker.boolean(),
            "additional_information": faker.paragraph(nb_sentences=5),
            "last_contact_date": dateparse.parse_date(faker.date()),
            "has_children": faker.boolean(),
            "is_age_over_55": faker.boolean(),
        }

    encrypted_field_map = {
        "is_right_of_occupancy_housing_changer": BooleanPGPPublicKeyField,
        "has_hitas_ownership": BooleanPGPPublicKeyField,
        "right_of_residence": IntegerPGPPublicKeyField,
        "right_of_residence_is_old_batch": BooleanPGPPublicKeyField,
        "additional_information": pgcrypto.fields.TextPGPPublicKeyField,
        "last_contact_date": pgcrypto.fields.DatePGPPublicKeyField,
        "has_children": pgcrypto.fields.BooleanPGPPublicKeyField,
        "is_age_over_55": pgcrypto.fields.BooleanPGPPublicKeyField,
    }

    decrypted_field_map = {
        "is_right_of_occupancy_housing_changer": models.BooleanField,
        "has_hitas_ownership": models.BooleanField,
        "right_of_residence": models.IntegerField,
        "right_of_residence_is_old_batch": models.BooleanField,
        "additional_information": models.TextField,
        "last_contact_date": models.DateField,
        "has_children": models.BooleanField,
        "is_age_over_55": models.BooleanField,
    }

    customer_1_test_data = get_test_data()
    customer_2_test_data = get_test_data()

    customer_1 = OldCustomer.objects.create(
        primary_profile=profile_1,
        **customer_1_test_data,
    )

    customer_2 = OldCustomer.objects.create(
        primary_profile=profile_2,
        **customer_2_test_data,
    )

    # Verify forward migrate

    new_state = migrator.apply_tested_migration(("customer", "0007_decrypt_customer"))

    NewCustomer: Model = new_state.apps.get_model("customer", "Customer")

    def assert_field_type(model, field_name, expected_type):
        assert (field_name, type(model._meta.get_field(field_name))) == (
            field_name,
            expected_type,
        )

    for k, v in decrypted_field_map.items():
        assert_field_type(NewCustomer, k, v)

    assert NewCustomer.objects.all().count() == 2
    customer_1 = NewCustomer.objects.get(pk=customer_1.pk)
    customer_2 = NewCustomer.objects.get(pk=customer_2.pk)

    for k, v in customer_1_test_data.items():
        assert getattr(customer_1, k) == v

    for k, v in customer_2_test_data.items():
        assert getattr(customer_2, k) == v

    # Verify backward migrate

    reverted_state = migrator.apply_tested_migration(
        ("customer", "0005_add_right_of_residence_is_old_batch")
    )

    RevertedCustomer: Model = reverted_state.apps.get_model("customer", "Customer")

    for k, v in encrypted_field_map.items():
        assert_field_type(RevertedCustomer, k, v)

    assert RevertedCustomer.objects.all().count() == 2
    customer_1 = RevertedCustomer.objects.get(pk=customer_1.pk)
    customer_2 = RevertedCustomer.objects.get(pk=customer_2.pk)

    for k, v in customer_1_test_data.items():
        assert getattr(customer_1, k) == v

    for k, v in customer_2_test_data.items():
        assert getattr(customer_2, k) == v
