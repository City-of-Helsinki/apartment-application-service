import uuid
from datetime import date

import pgcrypto.fields
import pytest
from django.db import models
from django.db.models import Model

from invoicing.enums import InstallmentType


@pytest.mark.django_db(transaction=True)
def test_0016_decrypt_apartmentinstallment(migrator):
    old_state = migrator.apply_initial_migration(
        ("invoicing", "0015_alter_apartmentinstallment_invoice_number")
    )
    OldProfile: Model = old_state.apps.get_model("users", "Profile")
    OldCustomer: Model = old_state.apps.get_model("customer", "Customer")

    OldApartmentReservation: Model = old_state.apps.get_model(
        "application_form", "ApartmentReservation"
    )
    OldApartmentInstallment: Model = old_state.apps.get_model(
        "invoicing", "ApartmentInstallment"
    )

    handler_1 = "Test 1"
    handler_2 = "Test 2"

    profile_1 = OldProfile.objects.create(date_of_birth=date.today())

    customer_1 = OldCustomer.objects.create(
        primary_profile=profile_1,
    )

    apartment_reservation_1 = OldApartmentReservation.objects.create(
        apartment_uuid=uuid.uuid4(),
        customer=customer_1,
        list_position=1,
    )
    apartment_installment_1 = OldApartmentInstallment.objects.create(
        type=InstallmentType.PAYMENT_1,
        value=0,
        apartment_reservation=apartment_reservation_1,
        invoice_number=1,
        reference_number="a",
        handler=handler_1,
    )

    apartment_installment_2 = OldApartmentInstallment.objects.create(
        type=InstallmentType.PAYMENT_2,
        value=0,
        apartment_reservation=apartment_reservation_1,
        invoice_number=2,
        reference_number="b",
        handler=handler_2,
    )
    new_state = migrator.apply_tested_migration(
        ("invoicing", "0016_decrypt_apartmentinstallment")
    )

    NewApartmentInstallment: Model = new_state.apps.get_model(
        "invoicing", "ApartmentInstallment"
    )

    def assert_field_type(model, field_name, expected_type):
        assert type(model._meta.get_field(field_name)) == expected_type

    # Verify migrated model has expected field types
    assert_field_type(NewApartmentInstallment, "handler", models.CharField)
    assert NewApartmentInstallment.objects.all().count() == 2
    apartment_installment_1 = NewApartmentInstallment.objects.get(
        pk=apartment_installment_1.pk
    )
    apartment_installment_2 = NewApartmentInstallment.objects.get(
        pk=apartment_installment_2.pk
    )
    assert apartment_installment_1.handler == handler_1
    assert apartment_installment_2.handler == handler_2

    reverted_state = migrator.apply_tested_migration(
        ("invoicing", "0015_alter_apartmentinstallment_invoice_number")
    )

    RevertedApartmentInstallment: Model = reverted_state.apps.get_model(
        "invoicing", "ApartmentInstallment"
    )
    assert_field_type(
        RevertedApartmentInstallment, "handler", pgcrypto.fields.CharPGPPublicKeyField
    )

    assert RevertedApartmentInstallment.objects.all().count() == 2
    apartment_installment_1 = RevertedApartmentInstallment.objects.get(
        pk=apartment_installment_1.pk
    )
    apartment_installment_2 = RevertedApartmentInstallment.objects.get(
        pk=apartment_installment_2.pk
    )
    assert apartment_installment_1.handler == handler_1
    assert apartment_installment_2.handler == handler_2
