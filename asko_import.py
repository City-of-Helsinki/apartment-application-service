import csv
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

import os
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
    ApplicationType,
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
from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate
from users.models import Profile

ADDED_TO_SAP_AT = datetime(2022, 1, 1)
DEFAULT_OFFER_VALID_UNTIL = date(2022, 10, 10)
DEFAULT_SSN_SUFFIX = "XXXXX"
DEFAULT_AGE = 1000
DEFAULT_DATE_OR_BIRTH = date(1900, 1, 1)

# TODO
# TEMP stuff for getting valid apartment UUIDs
# As Oy Helsingin Hitaskohde
HITAS_PROJECT_UUID = "1977dbd6-c9b1-537a-a975-13ba2f1f5abb"
HASO_PROJECT_UUID = "c4782874-6164-43e7-99b5-4dcd65d8cc62"
hitas_apartment_uuids = get_apartment_uuids(HITAS_PROJECT_UUID)
haso_apartment_uuids = get_apartment_uuids(HASO_PROJECT_UUID)
all_apartment_uuids = hitas_apartment_uuids + haso_apartment_uuids

apartment_uuid_map = {}


@lru_cache()
def get_hitas_apartment_uuid(asko_id):
    new_uuid = hitas_apartment_uuids.pop()
    apartment_uuid_map[asko_id] = new_uuid
    return new_uuid


@lru_cache()
def get_haso_apartment_uuid(asko_id):
    new_uuid = haso_apartment_uuids.pop()
    apartment_uuid_map[asko_id] = new_uuid
    return new_uuid


def get_apartment_uuid(asko_id):
    return apartment_uuid_map.get(asko_id)


def get_project_uuid(asko_id):
    if asko_id == "36":
        return HITAS_PROJECT_UUID
    elif asko_id == "38":
        return HASO_PROJECT_UUID
    else:
        raise Exception(f"Invalid project id {asko_id}")


class ModelStore:
    data = defaultdict(dict)

    def get(self, model, asko_id):
        try:
            return self.data[model][asko_id]
        except AttributeError:
            raise Exception(f"{model} asko_id {asko_id} not saved!")

    def get_instances(self, model):
        return self.data[model].values()

    def get_ids(self, model):
        return [o.pk for o in self.get_instances(model)]

    def put(self, asko_id, instance):
        model = type(instance)
        if model not in self.data or asko_id not in self.data[model]:
            self.data[model][asko_id] = instance

    def get_apartment_uuids(self):
        return set(r.apartment_uuid for r in self.data[ApartmentReservation].values())

    def get_hitas_apartment_uuids(self):
        return set(
            r.apartment_uuid
            for r in self.data[ApartmentReservation].values()
            if r.application_apartment.application.type
            in (ApplicationType.HITAS, ApplicationType.PUOLIHITAS)
        )

    def get_haso_apartment_uuids(self):
        return set(
            r.apartment_uuid
            for r in self.data[ApartmentReservation].values()
            if r.application_apartment.application.type == ApplicationType.HASO
        )


_model_store = ModelStore()


class CustomBooleanField(serializers.BooleanField):
    def to_internal_value(self, data):
        if data == "0":
            return False
        elif data == "-1":
            return True
        return super().to_internal_value(data)


class CustomDateField(serializers.DateField):
    def __init__(self, *args, **kwargs):
        kwargs["input_formats"] = ["%d.%m.%Y", "%d.%m.%Y %H:%M:%S"]
        super().__init__(*args, **kwargs)


class CustomDateTimeField(serializers.DateTimeField):
    def __init__(self, *args, **kwargs):
        kwargs["input_formats"] = ["%d.%m.%Y %H:%M:%S"]
        super().__init__(*args, **kwargs)


class CustomDecimalField(serializers.DecimalField):
    def to_internal_value(self, data):
        if type(data) is str:
            data = data.replace(" ", "").replace(",", ".").replace("€", "")
        return super().to_internal_value(data)


class CustomPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def to_internal_value(self, data):
        return super().to_internal_value(_model_store.get(self.queryset.model, data).pk)


class CustomModelSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.serializer_field_mapping[models.BooleanField] = CustomBooleanField
        self.serializer_field_mapping[models.DateField] = CustomDateField
        self.serializer_field_mapping[models.DateTimeField] = CustomDateTimeField
        self.serializer_field_mapping[models.DecimalField] = CustomDecimalField
        self.serializer_related_field = CustomPrimaryKeyRelatedField


class ProfileSerializer(CustomModelSerializer):
    email = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    date_of_birth = CustomDateField(required=False)

    class Meta:
        model = Profile
        fields = "__all__"

    def to_internal_value(self, data):
        data["contact_language"] = "fi"
        return super().to_internal_value(data)


class CustomerSerializer(CustomModelSerializer):
    last_contact_date = CustomDateField(required=False)

    class Meta:
        model = Customer
        fields = "__all__"


class ApplicantSerializer(CustomModelSerializer):
    application = CustomPrimaryKeyRelatedField(queryset=Application.objects.all())
    email = serializers.CharField(required=False)
    phone_number = serializers.CharField(required=False)
    street_address = serializers.CharField(required=False)
    postal_code = serializers.CharField(required=False)
    city = serializers.CharField(required=False)
    date_of_birth = CustomDateField(required=False, default=DEFAULT_DATE_OR_BIRTH)
    age = serializers.IntegerField(required=False, default=DEFAULT_AGE)
    ssn_suffix = serializers.CharField(required=False, default=DEFAULT_SSN_SUFFIX)

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


class ApplicationSerializer(EnumSupportSerializerMixin, serializers.ModelSerializer):
    customer = CustomPrimaryKeyRelatedField(queryset=Customer.objects.all())
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
        # will be populated later
        # TODO
        data["applicants_count"] = 0
        return super().to_internal_value(data)


class ApartmentReservationSerializer(
    EnumSupportSerializerMixin, serializers.ModelSerializer
):
    application_apartment = CustomPrimaryKeyRelatedField(
        queryset=ApplicationApartment.objects.all()
    )

    class Meta:
        model = ApartmentReservation
        fields = (
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
        data["customer"] = _model_store.get(Customer, data["customer"]).pk

        # will be populated later
        data["list_position"] = 0

        data = super().to_internal_value(data)

        data["right_of_residence"] = data[
            "application_apartment"
        ].application.right_of_residence
        return data


class ApplicationApartmentSerializer(serializers.ModelSerializer):
    application = CustomPrimaryKeyRelatedField(queryset=Application.objects.all())

    class Meta:
        model = ApplicationApartment
        fields = ("application", "apartment_uuid", "priority_number")

    def to_internal_value(self, data):
        ownership_type = "haso" if data["id"].startswith("1000") else "hitas"
        data["apartment_uuid"] = (
            get_hitas_apartment_uuid(data["apartment_uuid"])
            if ownership_type == "hitas"
            else get_haso_apartment_uuid(data["apartment_uuid"])
        )
        return super().to_internal_value(data)


class ProjectInstallmentTemplateSerializer(CustomModelSerializer):
    due_date = CustomDateField(required=False)

    class Meta:
        model = ProjectInstallmentTemplate
        fields = "__all__"

    def to_internal_value(self, data):
        data["project_uuid"] = get_project_uuid(data["project_uuid"])

        if not data.get("percentage_specifier"):
            data["percentage_specifier"] = "SALES_PRICE"

        return super().to_internal_value(data)


class ApartmentInstallmentSerializer(CustomModelSerializer):
    due_date = serializers.DateField(required=False, input_formats=["%d.%m.%Y %H:%M:%S"])

    class Meta:
        model = ApartmentInstallment
        exclude = ("added_to_be_sent_to_sap_at",)

    def to_internal_value(self, data):
        data["added_to_be_sent_to_sap_at"] = ADDED_TO_SAP_AT
        data["sent_to_sap_at"] = ADDED_TO_SAP_AT

        return super().to_internal_value(data)


class LotteryEventSerializer(CustomModelSerializer):
    class Meta:
        model = LotteryEvent
        fields = ("apartment_uuid", "timestamp")

    def to_internal_value(self, data):
        data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])
        return super().to_internal_value(data)


class LotteryEventResultSerializer(CustomModelSerializer):
    class Meta:
        model = LotteryEventResult
        fields = ("event", "application_apartment", "result_position")


class OfferSerializer(CustomModelSerializer):
    valid_until = CustomDateField(required=False, default=DEFAULT_OFFER_VALID_UNTIL)
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
        if "state" in data:
            data["state"] = data["state"].lower()
        return super().to_internal_value(data)


def _delete_existing_data():
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

    customer_ids = Customer.objects.filter(
        apartment_reservations__apartment_uuid__in=all_apartment_uuids
    ).values_list("id", flat=True)

    Profile.objects.filter(customers_where_primary__id__in=customer_ids).delete()
    Profile.objects.filter(customers_where_secondary__id__in=customer_ids).delete()

    Application.objects.filter(
        application_apartments__apartment_uuid__in=all_apartment_uuids
    ).delete()
    ApplicationApartment.objects.filter(apartment_uuid__in=all_apartment_uuids).delete()

    ProjectInstallmentTemplate.objects.filter(
        project_uuid__in=(HITAS_PROJECT_UUID, HASO_PROJECT_UUID)
    ).delete()


def _import_data(directory=None, ignore_errors=False):
    directory = directory or "asko_data/100822/"

    def import_model(
        filename: str, serializer_class: type(serializers.ModelSerializer)
    ) -> Tuple[int, int]:
        rows = 0
        imported = 0
        name = serializer_class.Meta.model.__name__
        file_path = os.path.join(directory, filename)

        with open(file_path, mode="r", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=";")
            for row in reader:
                rows += 1
                row = {k.lower(): v for k, v in row.items() if v != ""}
                serializer = serializer_class(data=row)
                try:
                    serializer.is_valid(raise_exception=True)
                except Exception as e:
                    if ignore_errors:
                        print(f"Cannot import {name} {row}, exception: {e}\n")
                        continue
                    else:
                        raise
                instance = serializer.save()
                _model_store.put(row["id"], instance)
                imported += 1

        print(f"*** Imported {imported} / {rows} {name} ***")

        return imported, rows

    # TODO remove these
    import_model("profile.txt", ProfileSerializer)
    import_model("customer.txt", CustomerSerializer)

    import_model("application.txt", ApplicationSerializer)
    import_model("applicant.txt", ApplicantSerializer)
    import_model("ApplicationApartment.txt", ApplicationApartmentSerializer)
    import_model("ApartmentReservation.txt", ApartmentReservationSerializer)

    # import_model("Offer.txt", OfferSerializer)

    import_model("ProjectInstallmentTemplate.txt", ProjectInstallmentTemplateSerializer)
    import_model("ApartmentInstallment.txt", ApartmentInstallmentSerializer)
    import_model("LotteryEvent.txt", LotteryEventSerializer)
    import_model("LotteryEventResult.txt", LotteryEventResultSerializer)



def _set_hitas_reservation_positions():
    for apartment_uuid in _model_store.get_hitas_apartment_uuids():
        reservations = ApartmentReservation.objects.filter(
            id__in=_model_store.get_ids(ApartmentReservation),
            apartment_uuid=apartment_uuid,
        )
        reservations_and_positions = (
            (
                reservation,
                LotteryEventResult.objects.get(
                    application_apartment=reservation.application_apartment
                ).result_position,
            )
            for reservation in reservations
        )
        ordered_reservations = (
            r[0] for r in sorted(reservations_and_positions, key=lambda x: x[1])
        )

        _set_reservation_positions(ordered_reservations)


def _set_haso_reservation_positions():
    for apartment_uuid in _model_store.get_haso_apartment_uuids():
        reservations = ApartmentReservation.objects.filter(
            id__in=_model_store.get_ids(ApartmentReservation),
            apartment_uuid=apartment_uuid,
        )
        reservations_and_positions = (
            (reservation, reservation.right_of_residence or float("inf"))
            for reservation in reservations
        )
        ordered_reservations = (
            r[0] for r in sorted(reservations_and_positions, key=lambda x: x[1])
        )

        lottery_event = LotteryEvent.objects.create(apartment_uuid=apartment_uuid)
        _set_reservation_positions(ordered_reservations, lottery_event=lottery_event)


def _set_reservation_positions(reservations, lottery_event=None):
    queue_position = 0
    for list_position, reservation in enumerate(reservations, 1):
        if reservation.state != ApartmentReservationState.CANCELED:
            queue_position += 1

        if (
            queue_position == 1
            and reservation.state == ApartmentReservationState.SUBMITTED
        ):
            reservation.state = ApartmentReservationState.RESERVED
        elif (
            queue_position > 1
            and reservation.state != ApartmentReservationState.SUBMITTED
        ):
            reservation.state = ApartmentReservationState.SUBMITTED

        ApartmentReservation.objects.filter(pk=reservation.pk).update(
            state=reservation.state,
            list_position=list_position,
            queue_position=queue_position
            if reservation.state != ApartmentReservationState.CANCELED
            else None,
        )
        ApartmentReservationStateChangeEvent.objects.filter(pk=reservation.state_change_events.first().pk).update(
            state=reservation.state,
            comment="Tuotu AsKo:sta",
        )
        if lottery_event:
            LotteryEventResult.objects.create(
                event=lottery_event,
                application_apartment=reservation.application_apartment,
                result_position=list_position,
            )


def _validate_imported_data():
    for apartment_uuid in _model_store.get_apartment_uuids():
        if not LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).exists():
            print(f"LOTTERY DOES NOT EXIST FOR APARTMENT {apartment_uuid}")

    for reservation in ApartmentReservation.objects.filter(
        pk__in=_model_store.get_ids(ApartmentReservation)
    ):
        if not reservation.application_apartment:
            print(f"RESERVATION {reservation} DOES NOT HAVE AN APPLICATION")

        if (
            reservation.queue_position == 1
            and reservation.state == ApartmentReservationState.SUBMITTED
        ):
            print(
                f"RESERVATION {reservation} customer {reservation.customer} is in "
                f"wrong state"
            )

        if (
                reservation.queue_position is not None and reservation.queue_position != 1
                and reservation.state != ApartmentReservationState.SUBMITTED
        ):
            print(
                f"RESERVATION {reservation} customer {reservation.customer} should be "
                f"SUBMITTED but it is {reservation.state} on position {reservation.queue_position}"
            )


def run_asko_import(directory=None, commit=False, ignore_errors=False, **kwargs):
    print(f"Importing data from AsKo...")

    with transaction.atomic():
        global _model_store
        _model_store = ModelStore()
        _delete_existing_data()
        _import_data(directory=directory, ignore_errors=ignore_errors)
        print("Setting reservation positions...")
        _set_hitas_reservation_positions()
        _set_haso_reservation_positions()
        print("Validating imported data...")
        _validate_imported_data()

        if not commit:
            transaction.set_rollback(True)

    print("All done!")
