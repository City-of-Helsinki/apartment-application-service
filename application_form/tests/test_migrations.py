import random
import uuid
from datetime import date

import pgcrypto.fields
import pytest
from django.db import models
from django.db.models import Model
from enumfields import EnumField
from faker import Faker
from pgcrypto.fields import IntegerPGPPublicKeyField

from apartment_application_service.fields import (
    BooleanPGPPublicKeyField,
    EnumPGPPublicKeyField,
    UUIDPGPPublicKeyField,
)
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


def test_0073_decrypt_application(migrator):  # noqa: C901
    faker = Faker()
    old_state = migrator.apply_initial_migration(
        ("application_form", "0072_decrypt_common_application_data")
    )
    OldProfile: Model = old_state.apps.get_model("users", "Profile")
    OldCustomer: Model = old_state.apps.get_model("customer", "Customer")
    OldApplication: Model = old_state.apps.get_model("application_form", "Application")
    OldApplicant: Model = old_state.apps.get_model("application_form", "Applicant")
    OldApplicationApartment: Model = old_state.apps.get_model(
        "application_form", "ApplicationApartment"
    )

    profile_1 = OldProfile.objects.create(date_of_birth=date.today())
    profile_2 = OldProfile.objects.create(date_of_birth=date.today())

    customer_1 = OldCustomer.objects.create(
        primary_profile=profile_1,
    )
    customer_2 = OldCustomer.objects.create(
        primary_profile=profile_2,
    )

    application_encrypted_field_map = {
        "applicants_count": IntegerPGPPublicKeyField,
        "external_uuid": UUIDPGPPublicKeyField,
        "has_children": BooleanPGPPublicKeyField,
        "sender_names": pgcrypto.fields.CharPGPPublicKeyField,
        "type": EnumPGPPublicKeyField,
    }

    application_decrypted_field_map = {
        "applicants_count": models.IntegerField,
        "external_uuid": models.UUIDField,
        "has_children": models.BooleanField,
        "sender_names": models.CharField,
        "type": EnumField,
    }

    applicant_encrypted_field_map = {
        "age": IntegerPGPPublicKeyField,
        "city": pgcrypto.fields.CharPGPPublicKeyField,
        "contact_language": pgcrypto.fields.CharPGPPublicKeyField,
        "email": pgcrypto.fields.EmailPGPPublicKeyField,
        "first_name": pgcrypto.fields.CharPGPPublicKeyField,
        "is_primary_applicant": BooleanPGPPublicKeyField,
        "last_name": pgcrypto.fields.CharPGPPublicKeyField,
        "phone_number": pgcrypto.fields.CharPGPPublicKeyField,
        "postal_code": pgcrypto.fields.CharPGPPublicKeyField,
        "street_address": pgcrypto.fields.CharPGPPublicKeyField,
        "date_of_birth": pgcrypto.fields.DatePGPPublicKeyField,  # bonus check
        "ssn_suffix": pgcrypto.fields.CharPGPPublicKeyField,  # bonus check
    }

    applicant_decrypted_field_map = {
        "age": models.IntegerField,
        "city": models.CharField,
        "contact_language": models.CharField,
        "email": models.EmailField,
        "first_name": models.CharField,
        "is_primary_applicant": models.BooleanField,
        "last_name": models.CharField,
        "phone_number": models.CharField,
        "postal_code": models.CharField,
        "street_address": models.CharField,
        "date_of_birth": pgcrypto.fields.DatePGPPublicKeyField,  # bonus check
        "ssn_suffix": pgcrypto.fields.CharPGPPublicKeyField,  # bonus check
    }

    application_apt_encrypted_field_map = {
        "priority_number": IntegerPGPPublicKeyField,
    }

    application_apt_decrypted_field_map = {
        "priority_number": models.IntegerField,
    }

    def get_application_test_data():
        return {
            "applicants_count": 1,
            "external_uuid": uuid.uuid4(),
            "has_children": faker.boolean(),
            "sender_names": faker.first_name(),
            "type": random.choice(
                [
                    ApplicationType.HITAS,
                    ApplicationType.HASO,
                    ApplicationType.PUOLIHITAS,
                ]
            ),
        }

    def get_applicant_test_data():
        return {
            "age": faker.random_number(digits=2),
            "city": faker.city(),
            "contact_language": faker.country_code(),
            "email": faker.email(),
            "first_name": faker.first_name(),
            "is_primary_applicant": faker.boolean(),
            "last_name": faker.last_name(),
            "phone_number": faker.phone_number(),
            "postal_code": str(faker.random_number(digits=5, fix_len=True)),
            "street_address": faker.address(),
        }

    def get_application_apt_test_data():
        return {"priority_number": faker.random_number()}

    application_1_test_data = get_application_test_data()
    application_2_test_data = get_application_test_data()

    application_1 = OldApplication.objects.create(
        customer=customer_1, **application_1_test_data
    )
    application_2 = OldApplication.objects.create(
        customer=customer_2, **application_2_test_data
    )

    applicant_1_test_data = get_applicant_test_data()
    applicant_2_test_data = get_applicant_test_data()

    applicant_1 = OldApplicant.objects.create(
        application=application_1, date_of_birth=date.today(), **applicant_1_test_data
    )
    applicant_2 = OldApplicant.objects.create(
        application=application_2, date_of_birth=date.today(), **applicant_2_test_data
    )

    application_apt_1_test_data = get_application_apt_test_data()
    application_apt_2_test_data = get_application_apt_test_data()

    application_apt_1 = OldApplicationApartment.objects.create(
        application=application_1,
        apartment_uuid=uuid.uuid4(),
        **application_apt_1_test_data,
    )
    application_apt_2 = OldApplicationApartment.objects.create(
        application=application_2,
        apartment_uuid=uuid.uuid4(),
        **application_apt_2_test_data,
    )

    new_state = migrator.apply_tested_migration(
        ("application_form", "0073_decrypt_application")
    )

    NewApplication: Model = new_state.apps.get_model("application_form", "Application")
    NewApplicant: Model = new_state.apps.get_model("application_form", "Applicant")
    NewApplicationApartment: Model = new_state.apps.get_model(
        "application_form", "ApplicationApartment"
    )

    def assert_field_type(model, field_name, expected_type):
        assert (field_name, type(model._meta.get_field(field_name))) == (
            field_name,
            expected_type,
        )

    for k, v in application_decrypted_field_map.items():
        assert_field_type(NewApplication, k, v)

    for k, v in applicant_decrypted_field_map.items():
        assert_field_type(NewApplicant, k, v)

    for k, v in application_apt_decrypted_field_map.items():
        assert_field_type(NewApplicationApartment, k, v)

    assert NewApplication.objects.all().count() == 2
    application_1 = NewApplication.objects.get(pk=application_1.pk)
    application_2 = NewApplication.objects.get(pk=application_2.pk)

    for k, v in application_1_test_data.items():
        assert getattr(application_1, k) == v

    for k, v in application_2_test_data.items():
        assert getattr(application_2, k) == v

    assert NewApplicant.objects.all().count() == 2
    applicant_1 = NewApplicant.objects.get(pk=applicant_1.pk)
    applicant_2 = NewApplicant.objects.get(pk=applicant_2.pk)

    for k, v in applicant_1_test_data.items():
        assert getattr(applicant_1, k) == v

    for k, v in applicant_2_test_data.items():
        assert getattr(applicant_2, k) == v

    assert NewApplicationApartment.objects.all().count() == 2
    application_apt_1 = NewApplicationApartment.objects.get(pk=application_apt_1.pk)
    application_apt_2 = NewApplicationApartment.objects.get(pk=application_apt_2.pk)

    for k, v in application_apt_1_test_data.items():
        assert getattr(application_apt_1, k) == v

    for k, v in application_apt_2_test_data.items():
        assert getattr(application_apt_2, k) == v

    revert_state = migrator.apply_tested_migration(
        ("application_form", "0072_decrypt_common_application_data")
    )

    RevertApplication: Model = revert_state.apps.get_model(
        "application_form", "Application"
    )
    RevertApplicant: Model = revert_state.apps.get_model(
        "application_form", "Applicant"
    )
    RevertApplicationApartment: Model = revert_state.apps.get_model(
        "application_form", "ApplicationApartment"
    )

    def assert_field_type(model, field_name, expected_type):
        assert (field_name, type(model._meta.get_field(field_name))) == (
            field_name,
            expected_type,
        )

    for k, v in application_encrypted_field_map.items():
        assert_field_type(RevertApplication, k, v)

    for k, v in applicant_encrypted_field_map.items():
        assert_field_type(RevertApplicant, k, v)

    for k, v in application_apt_encrypted_field_map.items():
        assert_field_type(RevertApplicationApartment, k, v)

    assert RevertApplication.objects.all().count() == 2
    application_1 = RevertApplication.objects.get(pk=application_1.pk)
    application_2 = RevertApplication.objects.get(pk=application_2.pk)

    for k, v in application_1_test_data.items():
        assert getattr(application_1, k) == v

    for k, v in application_2_test_data.items():
        assert getattr(application_2, k) == v

    assert RevertApplicant.objects.all().count() == 2
    applicant_1 = RevertApplicant.objects.get(pk=applicant_1.pk)
    applicant_2 = RevertApplicant.objects.get(pk=applicant_2.pk)

    for k, v in applicant_1_test_data.items():
        assert getattr(applicant_1, k) == v

    for k, v in applicant_2_test_data.items():
        assert getattr(applicant_2, k) == v

    assert RevertApplicationApartment.objects.all().count() == 2
    application_apt_1 = RevertApplicationApartment.objects.get(pk=application_apt_1.pk)
    application_apt_2 = RevertApplicationApartment.objects.get(pk=application_apt_2.pk)

    for k, v in application_apt_1_test_data.items():
        assert getattr(application_apt_1, k) == v

    for k, v in application_apt_2_test_data.items():
        assert getattr(application_apt_2, k) == v
