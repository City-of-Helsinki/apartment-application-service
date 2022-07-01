import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from django.db import models, transaction
from enumfields.drf import EnumSupportSerializerMixin
from functools import lru_cache
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from typing import Tuple

from apartment.elastic.queries import get_apartment_uuids
from application_form.enums import (
    ApartmentReservationCancellationReason,
    ApartmentReservationState,
    OfferState,
)
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
    ApplicationApartment,
    LotteryEvent,
    LotteryEventResult,
    Offer,
)
from customer.models import Customer
from invoicing.models import ApartmentInstallment
from users.models import Profile

THRESHOLD_DATE = datetime(2022, 6, 30)
ADDED_TO_SAP_AT = datetime(2022, 4, 1)
DEFAULT_OFFER_VALID_UNTIL = date(2022, 10, 10)

# mapping of all imported objects to their AsKo IDs
# {<model name>: {<AsKo ID>: <object>} }
id_mapping = defaultdict(dict)

# TODO
# TEMP stuff for getting valid apartment UUIDs
apartment_uuids = get_apartment_uuids(
    "1977dbd6-c9b1-537a-a975-13ba2f1f5abb"
) + get_apartment_uuids("c4782874-6164-43e7-99b5-4dcd65d8cc62")
all_apartment_uuids = apartment_uuids.copy()

hitas_apartment_uuids = get_apartment_uuids("1977dbd6-c9b1-537a-a975-13ba2f1f5abb")
haso_apartment_uuids = get_apartment_uuids("c4782874-6164-43e7-99b5-4dcd65d8cc62")

apartment_uuid_map = {}

used_hitas_apartment_uuids = []
used_haso_apartment_uuids = []


@lru_cache()
def get_apartment_uuid(int_id):
    return apartment_uuids.pop()


@lru_cache()
def get_hitas_apartment_uuid(int_id):
    new_uuid = hitas_apartment_uuids.pop()
    apartment_uuid_map[int_id] = new_uuid
    used_hitas_apartment_uuids.append(new_uuid)
    return new_uuid


@lru_cache()
def get_haso_apartment_uuid(int_id):
    new_uuid = haso_apartment_uuids.pop()
    apartment_uuid_map[int_id] = new_uuid
    used_haso_apartment_uuids.append(new_uuid)
    return new_uuid


def get_any_aparment_uuid(int_id):
    return apartment_uuid_map.get(int_id)


def import_model(
    filename: str, serializer_class: type(serializers.ModelSerializer)
) -> Tuple[int, int]:
    rows = 0
    imported = 0
    name = serializer_class.Meta.model.__name__
    file_path = "asko_data/300622/" + filename

    with open(file_path, mode="r", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        for row in reader:
            rows += 1
            row = {k.lower(): v for k, v in row.items() if v != ""}
            serializer = serializer_class(data=row)
            try:
                serializer.is_valid(raise_exception=True)
            except ValidationError as e:
                print(f"Cannot import {name} {row}, exception: {e}\n")
                # raise
                continue
            except Exception as e:
                print(e)
                continue
            instance = serializer.save()
            id_mapping[serializer.Meta.model.__name__][row["id"]] = instance.pk
            imported += 1

    print(f"*** Imported {imported} / {rows} {serializer.Meta.model.__name__} ***")

    return imported, rows


class CustomBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if data == "0":
            return False
        elif data == "-1":
            return True
        return super().to_internal_value(data)


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(
        input_formats=[
            "%d.%m.%Y",
        ],
        required=False,
    )

    class Meta:
        model = Profile
        fields = "__all__"

    def to_internal_value(self, data):
        data["contact_language"] = "fi"
        return super().to_internal_value(data)


class CustomRelatedField(serializers.RelatedField):
    def to_internal_value(self, data):
        return id_mapping[self.queryset.model.__name__].get(data)


class CustomPrimaryField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        return super().to_internal_value(
            id_mapping[self.queryset.model.__name__].get(data)
        )


class CustomDateField(serializers.DateField):
    def __init__(self, *args, **kwargs):
        kwargs["input_formats"] = ["%d.%m.%Y"]
        super().__init__(*args, **kwargs)


class CustomDateTimeField(serializers.DateTimeField):
    def __init__(self, *args, **kwargs):
        kwargs["input_formats"] = ["%d.%m.%Y"]
        super().__init__(*args, **kwargs)


class CustomModelSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serializer_field_mapping[models.DateField] = CustomDateField
        self.serializer_field_mapping[models.DateTimeField] = CustomDateTimeField
        self.serializer_related_field = CustomPrimaryField


class CustomerSerializer(CustomModelSerializer):
    last_contact_date = CustomDateField(required=False)

    class Meta:
        model = Customer
        fields = "__all__"


class ApplicantSerializer(CustomModelSerializer):
    application = CustomPrimaryField(queryset=Application.objects.all())
    email = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    date_of_birth = serializers.DateField(
        input_formats=[
            "%d.%m.%Y",
        ],
        required=False,
    )
    is_primary_applicant = CustomBooleanField()

    class Meta:
        model = Applicant
        fields = (
            "application",
            "age",
            "city",
            "date_of_birth",
            "email",
            "first_name",
            "last_name",
            "is_primary_applicant",
            "phone_number",
            "postal_code",
            "ssn_suffix",
            "street_address",
        )

    def to_internal_value(self, data):
        data["ssn_suffix"] = data.get("ssn_suffix") or "A1234"
        data["age"] = data.get("age") or 999
        data["date_of_birth"] = data.get("date_of_birth") or date(1900, 1, 1)
        return super().to_internal_value(data)


class ApplicationSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    customer = CustomPrimaryField(queryset=Customer.objects.all())
    has_children = CustomBooleanField()
    has_hitas_ownership = CustomBooleanField()
    is_right_of_occupancy_housing_changer = CustomBooleanField()
    submitted_late = CustomBooleanField()

    class Meta:
        model = Application
        fields = (
            "id",
            "customer",
            "has_children",
            "has_hitas_ownership",
            "is_right_of_occupancy_housing_changer",
            "right_of_residence",
            "submitted_late",
            "type",
            "applicants_count",
        )

    def to_internal_value(self, data):
        # TODO
        data["applicants_count"] = 0
        return super().to_internal_value(data)


class ApartmentReservationSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    application_apartment = CustomPrimaryField(
        queryset=ApplicationApartment.objects.all()
    )

    class Meta:
        model = ApartmentReservation
        fields = (
            "queue_position",
            "state",
            "apartment_uuid",
            "customer",
            "list_position",
            "application_apartment",
            "right_of_residence",
        )

    def to_internal_value(self, data):
        ownership_type = "haso" if data["id"].startswith("1000") else "hitas"
        data["apartment_uuid"] = (
            get_hitas_apartment_uuid(data["apartment_uuid"])
            if ownership_type == "hitas"
            else get_haso_apartment_uuid(data["apartment_uuid"])
        )
        data["state"] = data.pop("state").lower().replace(" ", "_")
        data["customer"] = id_mapping["Customer"].get(data["customer"])
        """
        data["list_position"] = (
            ApartmentReservation.objects.filter(
                apartment_uuid=data["apartment_uuid"]
            ).aggregate(max_list_position=Max("list_position"))["max_list_position"]
            or 0
        ) + 1
        """
        data["list_position"] = 0

        data = super().to_internal_value(data)

        data["right_of_residence"] = data[
            "application_apartment"
        ].application.right_of_residence
        return data


class ApplicationApartmentSerializer(serializers.ModelSerializer):
    application = CustomPrimaryField(queryset=Application.objects.all())

    class Meta:
        model = ApplicationApartment
        fields = ("application", "apartment_uuid", "priority_number")

    def to_internal_value(self, data):
        # data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])
        ownership_type = "haso" if data["id"].startswith("1000") else "hitas"
        data["apartment_uuid"] = (
            get_hitas_apartment_uuid(data["apartment_uuid"])
            if ownership_type == "hitas"
            else get_haso_apartment_uuid(data["apartment_uuid"])
        )
        return super().to_internal_value(data)


class ApartmentInstallmentSerializer(CustomModelSerializer):
    due_date = CustomDateField(required=False)

    class Meta:
        model = ApartmentInstallment
        fields = "__all__"

    def to_internal_value(self, data):
        """
        data["apartment_uuid"] = uuid5(
            uuid.UUID("2390f15e-3de3-4bf4-b0c1-5aa58f2f646d"), data["apartment_uuid"]
        )
        data["state"] = data.pop("state").lower().replace(" ", "_")
        data["customer"] = id_mapping["Customer"].get(data["customer"])
        data["list_position"] = data.get("queue_position") or 99
        """
        data["added_to_be_sent_to_sap_at"] = ADDED_TO_SAP_AT
        data["value"] = Decimal(data["value"].replace(" ", "").replace(",", "."))
        if data["type"] == "RIGHT_OF_RESIDENCE_FEE":
            data["type"] = "RIGHT_OF_OCCUPANCY_PAYMENT"
        return super().to_internal_value(data)


class LotteryEventSerializer(CustomModelSerializer):
    class Meta:
        model = LotteryEvent
        fields = ("apartment_uuid", "timestamp")

    def to_internal_value(self, data):
        # data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])
        data["apartment_uuid"] = get_any_aparment_uuid(data["apartment_uuid"])
        return super().to_internal_value(data)


class LotteryEventResultSerializer(CustomModelSerializer):
    class Meta:
        model = LotteryEventResult
        fields = ("event", "application_apartment", "result_position")


class OfferSerializer(CustomModelSerializer):
    valid_until = CustomDateField(required=False)
    concluded_at = CustomDateTimeField(required=False)

    class Meta:
        model = Offer
        fields = (
            "apartment_reservation",
            "valid_until",
            "state",
            "concluded_at",
            "comment",
        )

    def to_internal_value(self, data):
        if not data.get("valid_until"):
            data["valid_until"] = DEFAULT_OFFER_VALID_UNTIL

        if "state" in data:
            data["state"] = data["state"].lower()
        return super().to_internal_value(data)


ApartmentInstallment.objects.filter(
    apartment_reservation__apartment_uuid__in=all_apartment_uuids
).delete()

Offer.objects.filter(
    apartment_reservation__apartment_uuid__in=all_apartment_uuids
).delete()
ApartmentReservation.objects.filter(apartment_uuid__in=all_apartment_uuids).delete()

LotteryEventResult.objects.filter(
    event__apartment_uuid__in=all_apartment_uuids
).delete()
LotteryEvent.objects.filter(apartment_uuid__in=all_apartment_uuids).delete()

LotteryEventResult.objects.filter(
    event__apartment_uuid__in=all_apartment_uuids
).delete()
LotteryEvent.objects.filter(apartment_uuid__in=all_apartment_uuids).delete()


Customer.objects.filter(apartment_uuid__in=all_apartment_uuids).delete()
Profile.objects.filter(customer__apartment_uuid__in=all_apartment_uuids).delete()
Application.objects.filter(
    application_apartments__apartment_uuid_in=all_apartment_uuids
).delete()
ApplicationApartment.objects.filter(apartment_uuid__in=all_apartment_uuids).delete()


with transaction.atomic():
    greatest_reservation_id = ApartmentReservation.objects.order_by("-id").first().id

    import_model("profile.csv", ProfileSerializer)
    import_model("customer.csv", CustomerSerializer)

    import_model(
        "application.csv",
        ApplicationSerializer,
    )
    import_model(
        "applicant.csv",
        ApplicantSerializer,
    )
    import_model(
        "ApplicationApartment.csv",
        ApplicationApartmentSerializer,
    )

    import_model(
        "ApartmentReservation.csv",
        ApartmentReservationSerializer,
    )
    import_model(
        "Offer.csv",
        OfferSerializer,
    )
    import_model(
        "ApartmentInstallment.csv",
        ApartmentInstallmentSerializer,
    )

    import_model(
        "LotteryEvent.csv",
        LotteryEventSerializer,
    )
    import_model(
        "LotteryEventResult.csv",
        LotteryEventResultSerializer,
    )

    for offer_id in id_mapping["Offer"].values():
        offer = Offer.objects.get(id=offer_id)
        if offer.state == OfferState.REJECTED:
            print(
                f"Offer {offer} is rejected, reservation {offer.apartment_reservation} is {offer.apartment_reservation.state}"
            )
            ApartmentReservation.objects.filter(
                pk=offer.apartment_reservation.pk
            ).update(state=ApartmentReservationState.CANCELED, queue_position=None)
            change_event = ApartmentReservationStateChangeEvent.objects.filter(
                reservation=offer.apartment_reservation,
            ).first()
            ApartmentReservationStateChangeEvent.objects.filter(
                pk=change_event.pk
            ).update(
                state=ApartmentReservationState.CANCELED,
                cancellation_reason=ApartmentReservationCancellationReason.CANCELED,
            )

    for apartment_uuid in used_hitas_apartment_uuids:
        reservations = ApartmentReservation.objects.filter(
            id__in=id_mapping["ApartmentReservation"].values(),
            apartment_uuid=apartment_uuid,
        )
        reservation_list = []
        no_position = []
        print("\nhandling HITAS apartment", apartment_uuid)
        print("reservations", reservations.count())

        for reservation in reservations:
            if reservation.queue_position and False:
                try:
                    lottery_event_result_position = LotteryEventResult.objects.get(
                        application_apartment=reservation.application_apartment
                    ).result_position
                    if reservation.queue_position != lottery_event_result_position:
                        print(
                            f"LOTTERY POSITION {lottery_event_result_position} DOES NOT MATCH QUEUE POSITION {reservation.queue_position}"
                        )
                except LotteryEventResult.DoesNotExist:
                    pass
                reservation_list.append((reservation.queue_position, reservation))
                continue
            try:
                # print("lottery apartaapp", reservation.application_apartment)
                lottery_event_result_position = LotteryEventResult.objects.get(
                    application_apartment=reservation.application_apartment
                ).result_position
                reservation_list.append((lottery_event_result_position, reservation))
            except LotteryEventResult.DoesNotExist:
                no_position.append(reservation)

        ordered_reservation_list = sorted(reservation_list, key=lambda x: x[0])
        list_position = 0
        queue_position = 0
        for _, reservation in ordered_reservation_list:
            list_position += 1
            if reservation.state != ApartmentReservationState.CANCELED:
                queue_position += 1
            ApartmentReservation.objects.filter(pk=reservation.pk).update(
                list_position=list_position,
                queue_position=queue_position
                if reservation.state != ApartmentReservationState.CANCELED
                else None,
            )

        for reservation in no_position:
            list_position += 1
            if reservation.state != ApartmentReservationState.CANCELED:
                queue_position += 1
            ApartmentReservation.objects.filter(pk=reservation.pk).update(
                list_position=list_position,
                queue_position=queue_position
                if reservation.state != ApartmentReservationState.CANCELED
                else None,
            )

    for apartment_uuid in used_haso_apartment_uuids:
        reservations = ApartmentReservation.objects.filter(
            id__in=id_mapping["ApartmentReservation"].values(),
            apartment_uuid=apartment_uuid,
        )
        reservation_list = []
        no_position = []
        print("handling HASO apartment", apartment_uuid)
        print("reservations", reservations.count())
        for reservation in reservations:
            if reservation.right_of_residence:
                reservation_list.append((reservation.right_of_residence, reservation))
            else:
                no_position.append(reservation)

        ordered_reservation_list = sorted(reservation_list, key=lambda x: x[0])
        list_position = 0
        queue_position = 0
        lottery_event = LotteryEvent.objects.create(apartment_uuid=apartment_uuid)
        for _, reservation in ordered_reservation_list:
            list_position += 1
            if reservation.state != ApartmentReservationState.CANCELED:
                queue_position += 1
            ApartmentReservation.objects.filter(pk=reservation.pk).update(
                list_position=list_position,
                queue_position=queue_position
                if reservation.state != ApartmentReservationState.CANCELED
                else None,
            )
            LotteryEventResult.objects.create(
                event=lottery_event,
                application_apartment=reservation.application_apartment,
                result_position=list_position,
            )
        for reservation in no_position:
            list_position += 1
            if reservation.state != ApartmentReservationState.CANCELED:
                queue_position += 1
            ApartmentReservation.objects.filter(pk=reservation.pk).update(
                list_position=list_position,
                queue_position=queue_position
                if reservation.state != ApartmentReservationState.CANCELED
                else None,
            )
            LotteryEventResult.objects.create(
                event=lottery_event,
                application_apartment=reservation.application_apartment,
                result_position=list_position,
            )

    for apartment_uuid in used_haso_apartment_uuids + used_hitas_apartment_uuids:
        if not LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).exists():
            print(
                "LOTTERY DOES NOT EXIST FOR %s (%s)"
                % (
                    apartment_uuid,
                    next(
                        a for a, b in apartment_uuid_map.items() if b == apartment_uuid
                    ),
                )
            )

    for reservation in ApartmentReservation.objects.filter(
        pk__in=id_mapping["ApartmentReservation"].values()
    ):
        if not reservation.application_apartment:
            print("RESERVATION DOES NOT HAVE AN APPLICATION", reservation)

    for app in ApplicationApartment.objects.filter(
        pk__in=id_mapping["ApplicationApartment"].values()
    ):
        try:
            app.apartment_reservation
        except ApplicationApartment.DoesNotExist:
            print("APP APARTMENT DOES NOT HAVE A RESERVATION", app)

    # raise Exception()
