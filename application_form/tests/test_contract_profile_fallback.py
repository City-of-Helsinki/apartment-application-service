from datetime import date, timedelta

import pytest

from apartment.enums import OwnershipType
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.pdf.haso import get_haso_contract_pdf_data
from application_form.pdf.hitas import get_hitas_contract_pdf_data
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicantFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from customer.tests.factories import CustomerFactory
from invoicing.enums import InstallmentType
from invoicing.tests.factories import ApartmentInstallmentFactory
from users.tests.factories import UserFactory


@pytest.mark.django_db
def test_hitas_contract_data_resolves_contact_fields_from_linked_applicant():
    """
    - Resolves missing and dash-like profile fields in HITAS contract data.
    - Uses linked reservation application primary applicant as fallback.
    """
    apartment = ApartmentDocumentFactory(
        project_ownership_type=OwnershipType.HITAS.value,
        project_use_complete_contract=False,
        stock_start_number="1",
        stock_end_number="100",
        project_contract_transfer_restriction=False,
        project_contract_article_of_association="",
        project_construction_permit_claim="",
        project_shares_transferred_when="",
        project_control_transferred_when="",
    )
    customer = CustomerFactory(
        primary_profile__email="-",
        primary_profile__phone_number="",
        primary_profile__street_address="-",
        primary_profile__postal_code="-",
        primary_profile__city="-",
    )
    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="hitas-linked@example.com",
        phone_number="0100200",
        street_address="Kekekatu 22",
        postal_code="00200",
        city="Helsinki",
    )
    application_apartment = ApplicationApartmentFactory(
        application=application,
        apartment_uuid=apartment.uuid,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        application_apartment=application_apartment,
    )

    due_date = date.today() + timedelta(days=30)
    for installment_type in (
        InstallmentType.PAYMENT_1,
        InstallmentType.PAYMENT_2,
        InstallmentType.PAYMENT_3,
        InstallmentType.PAYMENT_4,
        InstallmentType.PAYMENT_5,
        InstallmentType.PAYMENT_6,
        InstallmentType.PAYMENT_7,
        InstallmentType.DOWN_PAYMENT,
    ):
        ApartmentInstallmentFactory(
            apartment_reservation=reservation,
            type=installment_type,
            value=100000,
            due_date=due_date,
        )

    pdf_data = get_hitas_contract_pdf_data(
        apartment=apartment,
        reservation=reservation,
        sales_price_paid_place="Helsinki",
        sales_price_paid_time="18.8.2026",
        salesperson=UserFactory(),
    )

    assert pdf_data.occupant_1_email == "hitas-linked@example.com"
    assert pdf_data.occupant_1_phone_number == "0100200"
    assert "Kekekatu 22" in pdf_data.occupant_1_address
    assert "00200 Helsinki" in pdf_data.occupant_1_address


@pytest.mark.django_db
def test_haso_contract_data_resolves_contact_fields_from_linked_applicant():
    """
    - Resolves missing and dash-like profile fields in HASO contract data.
    - Uses linked reservation application primary applicant as fallback.
    """
    apartment = ApartmentDocumentFactory(
        project_ownership_type=OwnershipType.HASO.value
    )
    customer = CustomerFactory(
        primary_profile__email="-",
        primary_profile__phone_number="",
        primary_profile__street_address="-",
        primary_profile__postal_code="-",
        primary_profile__city="-",
    )
    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="haso-linked@example.com",
        phone_number="0100200",
        street_address="Kekekatu 22",
        postal_code="00200",
        city="Helsinki",
    )
    application_apartment = ApplicationApartmentFactory(
        application=application,
        apartment_uuid=apartment.uuid,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        application_apartment=application_apartment,
    )

    ApartmentInstallmentFactory(
        apartment_reservation=reservation,
        type=InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT,
        value=50000,
        due_date=date.today() + timedelta(days=14),
    )

    pdf_data = get_haso_contract_pdf_data(
        reservation=reservation,
        sales_price_paid_place="Helsinki",
        sales_price_paid_time="18.8.2026",
        salesperson=UserFactory(),
    )

    assert pdf_data.occupant_1_email == "haso-linked@example.com"
    assert pdf_data.occupant_1_phone_number == "0100200"
    assert "Kekekatu 22" in pdf_data.occupant_1_street_address
    assert "00200 Helsinki" in pdf_data.occupant_1_street_address


@pytest.mark.django_db
def test_hitas_contract_data_handles_missing_first_payment_installment():
    """
    - Does not crash when PAYMENT_1 installment is missing.
    - Keeps generating HITAS contract data for the reservation.
    """
    apartment = ApartmentDocumentFactory(
        project_ownership_type=OwnershipType.HITAS.value,
        project_use_complete_contract=False,
        stock_start_number="1",
        stock_end_number="100",
        project_contract_transfer_restriction=False,
        project_contract_article_of_association="",
        project_construction_permit_claim="",
        project_shares_transferred_when="",
        project_control_transferred_when="",
    )
    customer = CustomerFactory(primary_profile__email="-")
    application = ApplicationFactory(customer=customer)
    ApplicantFactory(
        application=application,
        is_primary_applicant=True,
        email="hitas-linked@example.com",
    )
    application_apartment = ApplicationApartmentFactory(
        application=application,
        apartment_uuid=apartment.uuid,
    )
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer=customer,
        application_apartment=application_apartment,
    )

    due_date = date.today() + timedelta(days=30)
    for installment_type in (
        InstallmentType.PAYMENT_2,
        InstallmentType.PAYMENT_3,
        InstallmentType.PAYMENT_4,
        InstallmentType.PAYMENT_5,
        InstallmentType.PAYMENT_6,
        InstallmentType.PAYMENT_7,
        InstallmentType.DOWN_PAYMENT,
    ):
        ApartmentInstallmentFactory(
            apartment_reservation=reservation,
            type=installment_type,
            value=100000,
            due_date=due_date,
        )

    pdf_data = get_hitas_contract_pdf_data(
        apartment=apartment,
        reservation=reservation,
        sales_price_paid_place="Helsinki",
        sales_price_paid_time="18.8.2026",
        salesperson=UserFactory(),
    )

    assert pdf_data is not None
    assert pdf_data.occupant_1_email == "hitas-linked@example.com"
