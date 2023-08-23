import csv
import os
from typing import Tuple, Type

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from application_form.enums import ApartmentReservationState
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Application,
    ApplicationApartment,
    LotteryEvent,
    LotteryEventResult,
    Offer,
)
from customer.models import Customer
from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate
from users.models import Profile

from .logger import LOG
from .object_store import get_object_store
from .serializers import (
    ApartmentInstallmentSerializer,
    ApartmentReservationSerializer,
    ApplicantSerializer,
    ApplicationApartmentSerializer,
    ApplicationSerializer,
    CustomerSerializer,
    LotteryEventResultSerializer,
    LotteryEventSerializer,
    ProfileSerializer,
    ProjectInstallmentTemplateSerializer,
)

_object_store = get_object_store()


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
        filename: str,
        serializer_class: Type[serializers.ModelSerializer],
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
    LOG.info("Starting AsKo import")
    with transaction.atomic():
        if flush_all:
            _flush()
            _flush_profiles()
        elif flush:
            _flush()
        else:
            _object_store.clear()

            _import_data(directory=directory, ignore_errors=ignore_errors)
            _set_hitas_reservation_positions()
            _set_haso_reservation_positions()
            _validate_imported_data()

        if not commit:
            print("Rolling back the changes...", end=" ")
            transaction.set_rollback(True)
            print("Done.")

    print("All done!")
