import pytest
import uuid
from datetime import date
from decimal import Decimal
from django.urls import reverse
from django.utils.timezone import localtime

from apartment.models import ProjectExtraData
from apartment.tests.factories import ApartmentDocumentFactory
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    ApplicationType,
)
from application_form.models import ApartmentReservation, LotteryEvent
from application_form.services.lottery.machine import distribute_apartments
from application_form.services.queue import add_application_to_queues
from application_form.tests.factories import (
    ApartmentReservationFactory,
    ApplicationFactory,
    OfferFactory,
)
from customer.tests.factories import CustomerFactory
from invoicing.enums import (
    InstallmentPercentageSpecifier,
    InstallmentType,
    InstallmentUnit,
)
from invoicing.tests.factories import (
    ApartmentInstallmentFactory,
    ProjectInstallmentTemplateFactory,
)
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_root_apartment_reservation_detail_unauthorized(
    user_api_client, elastic_project_with_5_apartments
):
    _, apartments = elastic_project_with_5_apartments
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartments[0].uuid, list_position=1
    )

    response = user_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_root_apartment_reservation_detail(
    salesperson_api_client, elastic_project_with_5_apartments
):
    _, apartments = elastic_project_with_5_apartments
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartments[0].uuid, list_position=1
    )
    installment = ApartmentInstallmentFactory(apartment_reservation=reservation)
    offer = OfferFactory(apartment_reservation=reservation)

    response = salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 200

    assert response.data == {
        "id": reservation.id,
        "installments": [
            {
                "type": installment.type.value,
                "amount": int(installment.value * 100),
                "account_number": installment.account_number,
                "reference_number": installment.reference_number,
                "due_date": str(installment.due_date),
                "added_to_be_sent_to_sap_at": None,
            }
        ],
        "installment_candidates": [],
        "apartment_uuid": reservation.apartment_uuid,
        "queue_position": None,
        "state": reservation.state.value,
        "lottery_position": None,
        "priority_number": reservation.application_apartment.priority_number,
        "customer_id": reservation.customer.id,
        "offer": {
            "id": offer.id,
            "created_at": localtime(offer.created_at).isoformat(),
            "valid_until": str(offer.valid_until),
            "state": offer.state.value,
            "concluded_at": offer.concluded_at,
            "comment": offer.comment,
            "is_expired": False,
        },
        "right_of_residence": reservation.right_of_residence,
        "has_children": reservation.has_children,
        "has_hitas_ownership": reservation.has_hitas_ownership,
        "is_age_over_55": reservation.is_age_over_55,
        "is_right_of_occupancy_housing_changer": reservation.is_right_of_occupancy_housing_changer,  # noqa: E501
    }


@pytest.mark.django_db
def test_root_apartment_reservation_detail_installment_candidates(
    salesperson_api_client,
):
    apartment = ApartmentDocumentFactory(
        sales_price=12345678, debt_free_sales_price=9876543  # 123456,78e and 98765,43e
    )
    project_uuid = apartment.project_uuid
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)
    installment_template_1 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.REFUND,
        value=Decimal("100.50"),
        unit=InstallmentUnit.EURO,
        due_date=date(2022, 1, 10),
    )
    installment_template_2 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.PAYMENT_1,
        value=Decimal("10"),
        unit=InstallmentUnit.PERCENT,
        percentage_specifier=InstallmentPercentageSpecifier.SALES_PRICE,
        due_date=None,
    )
    installment_template_3 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.PAYMENT_2,
        value=Decimal("0.7"),
        unit=InstallmentUnit.PERCENT,
        percentage_specifier=InstallmentPercentageSpecifier.DEBT_FREE_SALES_PRICE,
        due_date=None,
    )
    installment_template_4 = ProjectInstallmentTemplateFactory(
        project_uuid=project_uuid,
        type=InstallmentType.PAYMENT_3,
        value=Decimal("17.25"),
        unit=InstallmentUnit.PERCENT,
        percentage_specifier=InstallmentPercentageSpecifier.DEBT_FREE_SALES_PRICE_FLEXIBLE,  # noqa: E501
        due_date=None,
    )
    # another project
    ProjectInstallmentTemplateFactory(
        project_uuid=uuid.UUID("19867533-2a60-4b3f-b166-f13af513d2d2"),
        type=InstallmentType.PAYMENT_1,
        value=Decimal("53"),
        unit=InstallmentUnit.EURO,
        due_date=None,
    )

    response = salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 200

    installment_candidates = response.data["installment_candidates"]
    assert len(installment_candidates) == 4

    assert installment_candidates[0] == {
        "type": installment_template_1.type.value,
        "amount": 10050,
        "account_number": installment_template_1.account_number,
        "due_date": "2022-01-10",
    }

    assert installment_candidates[1] == {
        "type": installment_template_2.type.value,
        "amount": 1234568,  # 10% of 123456,78e in cents
        "account_number": installment_template_2.account_number,
        "due_date": None,
    }

    assert installment_candidates[2] == {
        "type": installment_template_3.type.value,
        "amount": 69136,  # 0,7% of 987654,43e in cents
        "account_number": installment_template_3.account_number,
        "due_date": None,
    }

    assert installment_candidates[3] == {
        "type": installment_template_4.type.value,
        "amount": 1703704,  # 17,25% of 987654,43e in cents
        "account_number": installment_template_4.account_number,
        "due_date": None,
    }


@pytest.mark.django_db
def test_contract_pdf_creation_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    response = user_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-contract",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.parametrize("ownership_type", ("HASO", "Hitas"))
@pytest.mark.django_db
def test_contract_pdf_creation(salesperson_api_client, ownership_type):
    apartment = ApartmentDocumentFactory(project_ownership_type=ownership_type)
    reservation = ApartmentReservationFactory(apartment_uuid=apartment.uuid)

    response = salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-contract",
            kwargs={"pk": reservation.id},
        ),
        format="json",
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"

    test_value = (
        apartment.project_contract_right_of_occupancy_payment_verification
        if ownership_type == "HASO"
        else apartment.project_realty_id
    )
    assert bytes(test_value, encoding="utf-8") in response.content


@pytest.mark.django_db
def test_apartment_reservation_set_state_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"state": "reserved"}
    response = user_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-set-state",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.parametrize("comment", ("Foo", ""))
@pytest.mark.django_db
def test_apartment_reservation_set_state(salesperson_api_client, comment):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"state": "reserved", "comment": comment}
    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-set-state",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert len(response.data.keys()) == 3
    assert response.data.pop("timestamp")
    assert response.data == {
        "state": "reserved",
        "comment": comment,
    }

    assert reservation.state_change_events.count() == 2
    state_change_event = reservation.state_change_events.last()
    assert state_change_event.timestamp
    assert state_change_event.state == ApartmentReservationState.RESERVED
    assert state_change_event.comment == comment
    assert state_change_event.user == salesperson_api_client.user


@pytest.mark.django_db
def test_apartment_reservation_canceling_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"cancellation_reason": "terminated", "comment": "Foo"}
    response = user_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 403


@pytest.mark.parametrize("ownership_type", ("Haso", "Puolihitas", "Hitas"))
@pytest.mark.django_db
def test_apartment_reservation_canceling(salesperson_api_client, ownership_type):
    apartment = ApartmentDocumentFactory(project_ownership_type=ownership_type)
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"cancellation_reason": "terminated", "comment": "Foo"}
    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 200

    assert len(response.data.keys()) == 4
    assert response.data.pop("timestamp")
    assert response.data == {
        "state": "canceled",
        "comment": "Foo",
        "cancellation_reason": "terminated",
    }

    assert reservation.state_change_events.count() == 2
    state_change_event = reservation.state_change_events.last()
    assert state_change_event.timestamp
    assert state_change_event.state == ApartmentReservationState.CANCELED
    assert state_change_event.cancellation_reason
    assert state_change_event.user == salesperson_api_client.user


@pytest.mark.django_db
def test_cannot_cancel_already_canceled_apartment_reservation(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
    )

    data = {"cancellation_reason": "terminated", "comment": "Foo"}
    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert "already canceled" in str(response.data)


@pytest.mark.django_db
def test_apartment_reservation_cancellation_reason_validation(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid, state=ApartmentReservationState.SUBMITTED
    )

    data = {"comment": "Foo"}
    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert "cancellation_reason" in str(response.data)


@pytest.mark.django_db
def test_apartment_reservation_hide_queue_position(
    salesperson_api_client, elastic_hitas_project_with_5_apartments
):
    project_uuid, apartments = elastic_hitas_project_with_5_apartments
    first_apartment_uuid = apartments[0].uuid
    app = ApplicationFactory(type=ApplicationType.HITAS)
    app_apartment = app.application_apartments.create(
        apartment_uuid=first_apartment_uuid, priority_number=0
    )
    add_application_to_queues(app)

    response = salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": app_apartment.apartment_reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 200

    assert response.data["queue_position"] is None

    distribute_apartments(project_uuid)

    response = salesperson_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-detail",
            kwargs={"pk": app_apartment.apartment_reservation.id},
        ),
        format="json",
    )
    assert response.status_code == 200

    assert response.data["queue_position"] == 1


@pytest.mark.django_db
def test_transfer_reservation_to_another_customer(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    another_customer = CustomerFactory()
    reservation_1 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.SUBMITTED,
        queue_position=1,
        list_position=1,
        customer=customer,
    )
    reservation_2 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.SUBMITTED,
        queue_position=2,
        list_position=2,
        customer=customer,
    )
    reservation_3 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.SUBMITTED,
        queue_position=3,
        list_position=3,
        customer=customer,
    )
    reservation_4 = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
        list_position=4,
        customer=customer,
    )

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation_2.id},
        ),
        data={
            "cancellation_reason": "transferred",
            "new_customer_id": another_customer.id,
            "comment": "foo",
        },
        format="json",
    )
    assert response.status_code == 200

    reservation_1.refresh_from_db()
    reservation_2.refresh_from_db()
    reservation_3.refresh_from_db()
    reservation_4.refresh_from_db()

    state_change_event = reservation_2.state_change_events.last()
    assert (
        state_change_event.cancellation_reason
        == ApartmentReservationCancellationReason.TRANSFERRED
    )
    assert state_change_event.comment == "foo"
    new_reservation = state_change_event.replaced_by

    assert len(response.data.keys()) == 6
    assert response.data.pop("timestamp")
    assert response.data == {
        "state": "canceled",
        "comment": "foo",
        "cancellation_reason": "transferred",
        "new_customer_id": another_customer.id,
        "new_reservation_id": new_reservation.id,
    }

    assert reservation_1.queue_position == 1
    assert reservation_1.list_position == 1

    assert reservation_2.customer == customer
    assert reservation_2.queue_position is None
    assert reservation_2.list_position == 2
    assert reservation_2.state == ApartmentReservationState.CANCELED

    assert new_reservation.customer == another_customer
    assert new_reservation.state == ApartmentReservationState.SUBMITTED
    assert new_reservation.queue_position == 2
    assert new_reservation.list_position == 3

    assert reservation_3.queue_position == 3
    assert reservation_3.list_position == 4

    assert reservation_4.queue_position is None
    assert reservation_4.list_position == 5


@pytest.mark.django_db
def test_transferring_apartment_reservation_requires_customer(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.SUBMITTED,
    )

    data = {"cancellation_reason": "transferred", "comment": "Foo"}
    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-cancel",
            kwargs={"pk": reservation.id},
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 400
    assert "new_customer_id is required" in str(response.data)


@pytest.mark.django_db
def test_create_reservation_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    LotteryEvent.objects.create(apartment_uuid=apartment.uuid)

    data = {
        "apartment_uuid": apartment.uuid,
        "customer_id": customer.id,
    }

    response = user_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.parametrize("include_read_only_fields", (False, True))
@pytest.mark.django_db
def test_create_reservation(salesperson_api_client, include_read_only_fields):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory(
        right_of_residence=777,
        has_children=None,
        has_hitas_ownership=None,
        is_age_over_55=True,
        is_right_of_occupancy_housing_changer=False,
    )
    LotteryEvent.objects.create(apartment_uuid=apartment.uuid)

    data = {
        "apartment_uuid": apartment.uuid,
        "customer_id": customer.id,
    }

    if include_read_only_fields:
        # try to set read only fields which should not be possible
        data.update(
            {
                "lottery_position": 8,
                "priority_number": 11,
                "queue_position": 4,
                "state": "offered",
                "has_children": True,
                "has_hitas_ownership": False,
                "is_age_over_55": None,
                "is_right_of_occupancy_housing_changer": None,
            }
        )

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 201

    assert response.data.pop("customer_id") == customer.id
    assert (reservation_id := response.data.pop("id"))
    assert response.data.pop("apartment_uuid") == apartment.uuid
    assert response.data == {
        "installments": [],
        "installment_candidates": [],
        "lottery_position": None,
        "queue_position": 1,
        "priority_number": None,
        "state": "reserved",
        "offer": None,
        "right_of_residence": 777,
        "has_children": None,
        "has_hitas_ownership": None,
        "is_age_over_55": True,
        "is_right_of_occupancy_housing_changer": False,
    }

    reservation = ApartmentReservation.objects.get(id=reservation_id)
    assert reservation.list_position == 1
    assert reservation.queue_position == 1
    assert reservation.state == ApartmentReservationState.RESERVED
    assert reservation.right_of_residence == 777
    assert reservation.has_children is None
    assert reservation.has_hitas_ownership is None
    assert reservation.is_age_over_55 is True
    assert reservation.is_right_of_occupancy_housing_changer is False


@pytest.mark.django_db
def test_create_reservation_lottery_not_executed(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()

    data = {
        "apartment_uuid": apartment.uuid,
        "customer_id": customer.id,
    }

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 400
    assert "lottery hasn't been executed yet" in str(response.data)


@pytest.mark.django_db
def test_create_reservation_lottery_non_existing_apartment(salesperson_api_client):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    LotteryEvent.objects.create(apartment_uuid=apartment.uuid)

    data = {
        "apartment_uuid": uuid.uuid4(),
        "customer_id": customer.id,
    }

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-list",
        ),
        data=data,
        format="json",
    )

    assert response.status_code == 400
    assert "doesn't exist" in str(response.data)


@pytest.mark.django_db
def test_create_reservation_queue_already_has_canceled_reservation(
    salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    LotteryEvent.objects.create(apartment_uuid=apartment.uuid)
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.CANCELED,
        queue_position=None,
        list_position=1,
    )

    data = {
        "apartment_uuid": apartment.uuid,
        "customer_id": customer.id,
    }

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-list",
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201

    assert response.data["state"] == "reserved"
    assert response.data["queue_position"] == 1


@pytest.mark.django_db
def test_create_reservation_queue_already_has_reserved_reservation(
    salesperson_api_client,
):
    apartment = ApartmentDocumentFactory()
    customer = CustomerFactory()
    LotteryEvent.objects.create(apartment_uuid=apartment.uuid)
    ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        state=ApartmentReservationState.RESERVED,
        queue_position=1,
        list_position=1,
    )

    data = {
        "apartment_uuid": apartment.uuid,
        "customer_id": customer.id,
    }

    response = salesperson_api_client.post(
        reverse(
            "application_form:sales-apartment-reservation-list",
        ),
        data=data,
        format="json",
    )
    assert response.status_code == 201

    assert response.data["state"] == "submitted"
    assert response.data["queue_position"] == 2


@pytest.mark.django_db
def test_get_offer_message_unauthorized(user_api_client):
    apartment = ApartmentDocumentFactory()

    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
    )

    response = user_api_client.get(
        reverse(
            "application_form:sales-apartment-reservation-offer-message",
            kwargs={"pk": reservation.id},
        ),
    )
    assert response.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("ownership_type", ["puolihitas", "hitas", "haso"])
def test_get_offer_message(salesperson_api_client, ownership_type):
    apartment = ApartmentDocumentFactory(
        apartment_number="A1",
        apartment_structure="5h+k",
        living_area=5.0,
        floor=3,
        sales_price=400000,
        debt_free_sales_price=500000,
        maintenance_fee=10000,
        right_of_occupancy_payment=30000,
        right_of_occupancy_fee=40000,
        right_of_occupancy_deposit=5000,
        project_ownership_type=ownership_type,
        project_housing_company="As Oy Pojanlohi",
    )

    ProjectExtraData.objects.create(
        project_uuid=apartment.project_uuid,
        offer_message_intro="this is intro\r\n",
        offer_message_content="this\r\nis\ncontent\r\n",
    )

    reservation = ApartmentReservationFactory(
        apartment_uuid=apartment.uuid,
        customer__right_of_residence=777,
        customer__is_age_over_55=True,
        customer__is_right_of_occupancy_housing_changer=False,
        customer__has_children=None,
        customer__primary_profile__first_name="Ulla",
        customer__primary_profile__last_name="Taalasmaa",
        customer__primary_profile__email="ulla@example.com",
    )

    url = reverse(
        "application_form:sales-apartment-reservation-offer-message",
        kwargs={"pk": reservation.id},
    ) + ("?valid_until=2022-03-04" if ownership_type == "haso" else "")
    response = salesperson_api_client.get(url)
    assert response.status_code == 200

    expected_subject = "Tarjous As Oy Pojanlohi A1"

    if ownership_type == "haso":
        expected_body = """this is intro

Huoneisto: A1
Huoneistotyyppi: 5h+k
Pinta-ala: 5.0
Kerros: 3. krs

Alustava asumisoikeusmaksu: 300,00 €
Alustava käyttövastike: 400,00 €
Käyttövakuus: 50,00 €

Asumisoikeusnumero: 777
Yli 55v: Kyllä
Asumisoikeusasunnon vaihtaja: Ei

Tarjouksen viimeinen voimassaolopäivä: 4.3.2022

this
is
content
""".replace(
            "\n", "\r\n"
        )
    else:
        expected_body = """this is intro

Huoneisto: A1
Huoneistotyyppi: 5h+k
Pinta-ala: 5.0
Kerros: 3. krs

Myyntihinta: 4 000,00 €
Velaton hinta: 5 000,00 €
Alustava vastike: 100,00 €

Lapsiperhe: Ei tiedossa

Tarjouksen viimeinen voimassaolopäivä: Ei tiedossa

this
is
content
""".replace(
            "\n", "\r\n"
        )

    expected_recipients = [
        {"name": "Ulla Taalasmaa", "email": "ulla@example.com"},
    ]

    expected_data = {
        "subject": expected_subject,
        "body": expected_body,
        "recipients": expected_recipients,
    }
    assert response.data == expected_data

    # test also with multiple recipients

    reservation.customer.secondary_profile = ProfileFactory(
        first_name="Suppo",
        last_name="Taalasmaa",
        email="suppo@example.com",
    )
    reservation.customer.save()

    response = salesperson_api_client.get(url)
    assert response.status_code == 200

    expected_data["recipients"].append(
        {"name": "Suppo Taalasmaa", "email": "suppo@example.com"},
    )
    assert response.data == expected_data
