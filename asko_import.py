import csv
import uuid
from collections import defaultdict
from datetime import date, datetime
from django.contrib.auth import get_user_model
from django.db import models, transaction
from enumfields.drf import EnumSupportSerializerMixin
from rest_framework import serializers
from typing import Tuple

from application_form.enums import ApartmentReservationState, ApplicationType
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

PROJECT_UUID_NAMESPACE = uuid.UUID("11111111-1111-1111-1111-111111111111")
APARTMENT_UUID_NAMESPACE = uuid.UUID("22222222-2222-2222-2222-222222222222")


def get_project_uuid(asko_id):
    return uuid.uuid5(PROJECT_UUID_NAMESPACE, asko_id)


def get_apartment_uuid(asko_id):
    return uuid.uuid5(APARTMENT_UUID_NAMESPACE, asko_id)


class ObjectStore:
    """Contains already imported objects grouped by their models."""

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


_object_store = ObjectStore()


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
        return super().to_internal_value(
            _object_store.get(self.queryset.model, data).pk
        )


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
        exclude = ("id",)


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
        data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])

        data["state"] = data.pop("state").lower().replace(" ", "_")
        data["customer"] = _object_store.get(Customer, data["customer"]).pk

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
        data["apartment_uuid"] = get_apartment_uuid(data["apartment_uuid"])
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
    due_date = serializers.DateField(
        required=False, input_formats=["%d.%m.%Y %H:%M:%S"]
    )

    class Meta:
        model = ApartmentInstallment
        fields = "__all__"

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


def _flush():
    print("Deleting everything other than Profiles and Users...", end=" ")
    ApartmentInstallment.objects.all().delete()
    Offer.objects.all().delete()
    ApartmentReservation.objects.all().delete()
    LotteryEventResult.objects.all().delete()
    LotteryEvent.objects.all().delete()
    Application.objects.all().delete()
    ApplicationApartment.objects.all().delete()
    ProjectInstallmentTemplate.objects.all().delete()
    Customer.objects.all().delete()
    print("Done.")


def _flush_profiles():
    print("Deleting Profiles and Users...", end=" ")
    get_user_model().objects.exclude(profile=None).delete()
    Profile.objects.all().delete()
    print("Done.")


def _import_data(directory=None, ignore_errors=False):
    directory = directory or ""

    def import_model(
        filename: str, serializer_class: type(serializers.ModelSerializer)
    ) -> Tuple[int, int]:
        imported = 0
        name = serializer_class.Meta.model.__name__ + "s"
        file_path = os.path.join(directory, filename)
        print(f"Importing {name}...", end=" ")

        with open(file_path, mode="r", encoding="utf-8-sig") as csv_file:
            reader = csv.DictReader(csv_file, delimiter=";")
            for index, row in enumerate(reader, 1):
                row = {k.lower(): v for k, v in row.items() if v != ""}
                serializer = serializer_class(data=row)
                try:
                    serializer.is_valid(raise_exception=True)
                    instance = serializer.save()
                except Exception as e:  # noqa
                    print(f"Cannot import {name} {row}, error: {e}")
                    if ignore_errors:
                        continue
                    else:
                        raise
                _object_store.put(row["id"], instance)
                imported += 1

        print(f"Done. Imported {imported} / {index} {name}")

        return imported, index

    print("Importing data from AsKo...")

    import_model("profile.txt", ProfileSerializer)
    import_model("customer.txt", CustomerSerializer)
    import_model("Application.txt", ApplicationSerializer)
    import_model("Applicant.txt", ApplicantSerializer)
    for application in _object_store.get_instances(Application):
        Application.objects.filter(pk=application.pk).update(
            applicants_count=application.applicants.count()
        )
    import_model("ApplicationApartment.txt", ApplicationApartmentSerializer)
    import_model("ApartmentReservation.txt", ApartmentReservationSerializer)
    import_model("ProjectInstallmentTemplate.txt", ProjectInstallmentTemplateSerializer)
    import_model("ApartmentInstallment.txt", ApartmentInstallmentSerializer)
    import_model("LotteryEvent.txt", LotteryEventSerializer)
    import_model("LotteryEventResult.txt", LotteryEventResultSerializer)


def _set_hitas_reservation_positions():
    print("Setting HITAS reservation positions...", end=" ")

    for apartment_uuid in _object_store.get_hitas_apartment_uuids():
        reservations = ApartmentReservation.objects.filter(
            id__in=_object_store.get_ids(ApartmentReservation),
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

    print("Done.")


def _set_haso_reservation_positions():
    print("Setting HASO reservation positions...", end=" ")

    for apartment_uuid in _object_store.get_haso_apartment_uuids():
        reservations = ApartmentReservation.objects.filter(
            id__in=_object_store.get_ids(ApartmentReservation),
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

    print("Done.")


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
        ApartmentReservationStateChangeEvent.objects.filter(
            pk=reservation.state_change_events.first().pk
        ).update(
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
    print("Validating imported data...", end=" ")

    for apartment_uuid in _object_store.get_apartment_uuids():
        if not LotteryEvent.objects.filter(apartment_uuid=apartment_uuid).exists():
            print(f"LOTTERY DOES NOT EXIST FOR APARTMENT {apartment_uuid}")

    for reservation in ApartmentReservation.objects.filter(
        pk__in=_object_store.get_ids(ApartmentReservation)
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
            reservation.queue_position is not None
            and reservation.queue_position != 1
            and reservation.state != ApartmentReservationState.SUBMITTED
        ):
            print(
                f"RESERVATION {reservation} customer {reservation.customer} should be "
                f"SUBMITTED but it is {reservation.state} in position "
                f"{reservation.queue_position}"
            )
    print("Done.")


def run_asko_import(
    directory=None,
    commit=False,
    ignore_errors=False,
    flush=False,
    flush_all=False,
):
    with transaction.atomic():
        if flush_all:
            _flush()
            _flush_profiles()
        elif flush:
            _flush()
        else:
            global _object_store
            _object_store = ObjectStore()

            _import_data(directory=directory, ignore_errors=ignore_errors)
            _set_hitas_reservation_positions()
            _set_haso_reservation_positions()
            _validate_imported_data()

        if not commit:
            print("Rolling back the changes...", end=" ")
            transaction.set_rollback(True)
            print("Done.")

    print("All done!")


# allows running like commit=1 ./manage.py shell < asko_import.py
if __name__ == "django.core.management.commands.shell":
    import os

    def get_boolean_env_var(var_name):
        return os.getenv(var_name, "False").lower() in ("true", "1", "t")

    directory = os.getenv("directory")
    commit = get_boolean_env_var("commit")
    ignore_errors = get_boolean_env_var("ignore_errors")
    flush = get_boolean_env_var("flush")
    flush_all = get_boolean_env_var("flush_all")

    run_asko_import(directory, commit, ignore_errors, flush, flush_all)
