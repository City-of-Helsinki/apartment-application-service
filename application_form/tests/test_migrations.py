import uuid
from datetime import date

import pgcrypto.fields
import pytest
from django.db import models
from django.db.models import Model
from faker import Faker
from pgcrypto.fields import IntegerPGPPublicKeyField

from apartment_application_service.fields import BooleanPGPPublicKeyField
from application_form.enums import ApplicationType


@pytest.mark.django_db
def test_0050_populate_apartment_reservation_customer(migrator):
    old_state = migrator.apply_initial_migration(
        ("application_form", "0049_apartmentreservation_customer")
    )

    Profile = old_state.apps.get_model("users", "Profile")
    Customer = old_state.apps.get_model("customer", "Customer")
    Application = old_state.apps.get_model("application_form", "Application")
    ApplicationApartment = old_state.apps.get_model(
        "application_form", "ApplicationApartment"
    )
    ApartmentReservation = old_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )

    apartment_uuid = uuid.uuid4()
    profile = Profile.objects.create(date_of_birth=date.today())
    customer = Customer.objects.create(primary_profile=profile)
    application = Application.objects.create(
        external_uuid=uuid.uuid4(),
        applicants_count=1,
        type=ApplicationType.HASO,
        customer=customer,
    )
    application_apartment = ApplicationApartment.objects.create(
        application=application, apartment_uuid=apartment_uuid, priority_number=1
    )
    apartment_reservation = ApartmentReservation.objects.create(
        apartment_uuid=apartment_uuid,
        queue_position=1,
        application_apartment=application_apartment,
    )

    new_state = migrator.apply_tested_migration(
        ("application_form", "0050_populate_apartment_reservation_customer")
    )

    ApartmentReservation = new_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )
    apartment_reservation = ApartmentReservation.objects.get(
        id=apartment_reservation.id
    )
    assert apartment_reservation.customer.id == customer.id
    # Clean up record so tearDown migrations does not break
    apartment_reservation.delete()
    application.delete()


@pytest.mark.django_db
def test_0072_decrypt_common_application_data(migrator):  # noqa: C901
    faker = Faker()
    old_state = migrator.apply_initial_migration(
        ("application_form", "0071_apartmentreservation_submitted_late")
    )
    Profile: Model = old_state.apps.get_model("users", "Profile")
    Customer: Model = old_state.apps.get_model("customer", "Customer")
    ApplicationApartment: Model = old_state.apps.get_model(
        "application_form", "ApplicationApartment"
    )
    ApartmentReservation: Model = old_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )
    Application: Model = old_state.apps.get_model("application_form", "Application")

    def get_common_application_test_data():
        return {
            "is_right_of_occupancy_housing_changer": faker.boolean(),
            "has_hitas_ownership": faker.boolean(),
            "right_of_residence": faker.random_number(),
            "right_of_residence_is_old_batch": faker.boolean(),
        }

    application_encrypted_field_map = {
        "is_right_of_occupancy_housing_changer": BooleanPGPPublicKeyField,
        "has_hitas_ownership": BooleanPGPPublicKeyField,
        "right_of_residence": IntegerPGPPublicKeyField,
        "right_of_residence_is_old_batch": BooleanPGPPublicKeyField,
    }

    apartment_reservation_encrypted_field_map = {
        "is_right_of_occupancy_housing_changer": pgcrypto.fields.BooleanPGPPublicKeyField,  # noqa: E501
        "has_hitas_ownership": pgcrypto.fields.BooleanPGPPublicKeyField,
        "right_of_residence": IntegerPGPPublicKeyField,
        "right_of_residence_is_old_batch": BooleanPGPPublicKeyField,
    }

    common_decrypted_field_map = {
        "is_right_of_occupancy_housing_changer": models.BooleanField,
        "has_hitas_ownership": models.BooleanField,
        "right_of_residence": models.IntegerField,
        "right_of_residence_is_old_batch": models.BooleanField,
    }

    application_1_test_data = get_common_application_test_data()
    application_2_test_data = get_common_application_test_data()
    apartment_reservation_1_test_data = get_common_application_test_data()
    apartment_reservation_2_test_data = get_common_application_test_data()

    profile = Profile.objects.create(date_of_birth=date.today())
    customer = Customer.objects.create(primary_profile=profile)
    application_1 = Application.objects.create(
        external_uuid=uuid.uuid4(),
        applicants_count=1,
        type=ApplicationType.HASO,
        customer=customer,
        **application_1_test_data,
    )
    application_2 = Application.objects.create(
        external_uuid=uuid.uuid4(),
        applicants_count=1,
        type=ApplicationType.HASO,
        customer=customer,
        **application_2_test_data,
    )
    application_apartment_1 = ApplicationApartment.objects.create(
        application=application_1, apartment_uuid=uuid.uuid4(), priority_number=1
    )
    apartment_reservation_1 = ApartmentReservation.objects.create(
        apartment_uuid=application_apartment_1.apartment_uuid,
        customer=customer,
        queue_position=1,
        list_position=1,
        application_apartment=application_apartment_1,
        **apartment_reservation_1_test_data,
    )
    application_apartment_2 = ApplicationApartment.objects.create(
        application=application_2, apartment_uuid=uuid.uuid4(), priority_number=1
    )
    apartment_reservation_2 = ApartmentReservation.objects.create(
        apartment_uuid=application_apartment_2.apartment_uuid,
        customer=customer,
        queue_position=1,
        list_position=1,
        application_apartment=application_apartment_2,
        **apartment_reservation_2_test_data,
    )
    new_state = migrator.apply_tested_migration(
        ("application_form", "0072_decrypt_common_application_data")
    )
    Application: Model = new_state.apps.get_model("application_form", "Application")
    ApartmentReservation: Model = new_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )

    def assert_field_type(model, field_name, expected_type):
        assert type(model._meta.get_field(field_name)) == expected_type

    # Verify migrated model has expected field types

    for k, v in common_decrypted_field_map.items():
        assert_field_type(Application, k, v)

    for k, v in common_decrypted_field_map.items():
        assert_field_type(ApartmentReservation, k, v)

    assert Application.objects.all().count() == 2
    application_1 = Application.objects.get(pk=application_1.pk)
    application_2 = Application.objects.get(pk=application_2.pk)

    for k, v in application_1_test_data.items():
        assert getattr(application_1, k) == v

    for k, v in application_2_test_data.items():
        assert getattr(application_2, k) == v

    assert ApartmentReservation.objects.all().count() == 2
    apartment_reservation_1 = ApartmentReservation.objects.get(
        pk=apartment_reservation_1.pk
    )
    apartment_reservation_2 = ApartmentReservation.objects.get(
        pk=apartment_reservation_2.pk
    )

    for k, v in apartment_reservation_1_test_data.items():
        assert getattr(apartment_reservation_1, k) == v

    for k, v in apartment_reservation_2_test_data.items():
        assert getattr(apartment_reservation_2, k) == v

    reverted_state = migrator.apply_tested_migration(
        ("application_form", "0071_apartmentreservation_submitted_late")
    )

    Application: Model = reverted_state.apps.get_model(
        "application_form", "Application"
    )
    ApartmentReservation: Model = reverted_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )

    for k, v in application_encrypted_field_map.items():
        assert_field_type(Application, k, v)

    for k, v in apartment_reservation_encrypted_field_map.items():
        assert_field_type(ApartmentReservation, k, v)

    assert Application.objects.all().count() == 2
    application_1 = Application.objects.get(pk=application_1.pk)
    application_2 = Application.objects.get(pk=application_2.pk)

    for k, v in application_1_test_data.items():
        assert getattr(application_1, k) == v

    for k, v in application_2_test_data.items():
        assert getattr(application_2, k) == v

    assert ApartmentReservation.objects.all().count() == 2
    apartment_reservation_1 = ApartmentReservation.objects.get(
        pk=apartment_reservation_1.pk
    )
    apartment_reservation_2 = ApartmentReservation.objects.get(
        pk=apartment_reservation_2.pk
    )

    for k, v in apartment_reservation_1_test_data.items():
        assert getattr(apartment_reservation_1, k) == v

    for k, v in apartment_reservation_2_test_data.items():
        assert getattr(apartment_reservation_2, k) == v
