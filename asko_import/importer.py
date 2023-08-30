import csv
import os
from typing import Tuple, Type

from django.contrib.auth import get_user_model
from django.db import models, transaction
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

from .duplicate_checker import DuplicateChecker
from .log_utils import log_debug_data
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
        skipped = 0
        model = serializer_class.Meta.model
        name = model.__name__
        duplicate_checker = DuplicateChecker(model)
        file_path = os.path.join(directory, filename)
        LOG.info("Importing %ss from %s", name, filename)

        with open(file_path, mode="r", encoding="utf-8-sig") as csv_file:
            count = sum(1 for _ in csv.DictReader(csv_file, delimiter=";"))
            print(f"[{count} entries]", end="", flush=True)
            csv_file.seek(0)

            reader = csv.DictReader(csv_file, delimiter=";")
            for index, row in enumerate(reader, 1):
                if index % 500 == 0:
                    if index % 5000 == 0:
                        print(f"({index})", end="", flush=True)
                    else:
                        print(".", end="", flush=True)
                row = {k.lower(): v for k, v in row.items() if v != ""}
                eid = row["id"]  # External ID (aka AsKo ID) of the row

                duplication_info = duplicate_checker.check(row)
                if duplication_info:
                    LOG.warning(
                        "Skipping import of %s asko_id=%s because %s",
                        name,
                        eid,
                        duplication_info,
                    )
                    skipped += 1
                    continue

                serializer = serializer_class(data=row)
                try:
                    serializer.is_valid(raise_exception=True)
                    instance = serializer.save()
                except Exception:
                    LOG.exception("Failed to import %s asko_id=%s", name, eid)
                    log_debug_data("Row data: %s", row)
                    if ignore_errors:
                        continue
                    else:
                        raise
                _object_store.put(eid, instance)
                imported += 1

        print("Done.")
        failed = count - imported - skipped
        LOG.info(
            "Imported %d %ss (skipped: %d, failed: %d)",
            imported,
            name,
            skipped,
            failed,
        )

        return imported, count

    print("Importing data from AsKo...")

    import_model("profile.txt", ProfileSerializer)
    import_model("customer.txt", CustomerSerializer)
    import_model("Application.txt", ApplicationSerializer)
    import_model("Applicant.txt", ApplicantSerializer)
    applications = _object_store.get_objects(Application)
    LOG.info("Updating applicants_count for %d applications", applications.count())
    for application in applications.annotate(ac=models.Count("applicants")):
        application_qs = Application.objects.filter(pk=application.pk)
        application_qs.update(applicants_count=application.ac)
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

    reservations = _object_store.get_objects(ApartmentReservation)
    apartment_uuids = reservations.values("apartment_uuid").distinct()
    apartment_uuids_without_lottery = apartment_uuids.exclude(
        apartment_uuid__in=LotteryEvent.objects.values("apartment_uuid")
    ).values_list("apartment_uuid", flat=True)
    for apartment_uuid in apartment_uuids_without_lottery:
        print(f"LOTTERY DOES NOT EXIST FOR APARTMENT {apartment_uuid}")

    for reservation in reservations:
        apartment_uuid = reservation.apartment_uuid

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
