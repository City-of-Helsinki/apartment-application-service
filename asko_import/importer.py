import contextlib
import csv
import os
from typing import Optional, Sequence, Tuple, Type

from django.contrib.auth import get_user_model
from django.db import models, transaction
from rest_framework import serializers

from application_form.enums import ApartmentReservationState
from application_form.models import (
    ApartmentReservation,
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

from .issues import DataIssueChecker
from .log_utils import log_context_from, log_debug_data
from .logger import LOG, log_context
from .models import AsKoImportLogEntry, AsKoLink
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


def run_asko_import(
    directory=None,
    commit=False,
    commit_each=False,
    skip_imported=False,
    ignore_errors=False,
    flush=False,
    flush_all=False,
    flush_reservations_etc=False,
):
    LOG.info("Starting AsKo import")

    if commit_each:
        outer_transaction = contextlib.nullcontext()
    else:
        outer_transaction = transaction.atomic()

    with outer_transaction:
        if flush_all:
            _flush()
            _flush_profiles()
        elif flush:
            _flush()
        elif flush_reservations_etc:
            _flush_reservations_etc()
        else:
            _object_store.clear()

            _import_data(directory, ignore_errors, skip_imported)

            _validate_imported_data()

        if not (commit or commit_each):
            print("Rolling back the changes...", end=" ", flush=True)
            transaction.set_rollback(True)
            print("Done.")

    print("All done!")


def _flush():
    print("Deleting everything other than Profiles and Users...")
    _flush_model(AsKoImportLogEntry)
    _flush_model(ApartmentInstallment)
    _flush_model(Offer)
    _flush_model(ApartmentReservation)
    _flush_model(LotteryEventResult)
    _flush_model(LotteryEvent)
    _flush_model(Application)
    _flush_model(Applicant)
    _flush_model(ApplicationApartment)
    _flush_model(ProjectInstallmentTemplate)
    _flush_model(Customer)
    _flush_model(AsKoLink)


def _flush_reservations_etc():
    print("Deleting reservations, installments and lottery events...")
    _flush_model(LotteryEventResult)
    _flush_model(LotteryEvent)
    _flush_model(ApartmentInstallment)
    _flush_model(ApartmentReservation)


def _flush_profiles():
    print("Deleting Profiles and Users...")
    _flush_qs(get_user_model().objects.exclude(profile=None))
    _flush_model(Profile)


def _flush_model(model):
    _flush_qs(model.objects.all())


def _flush_qs(qs):
    print(f"Deleting {qs.model.__name__}s...", end=" ", flush=True)
    asko_links = AsKoLink.get_objects_of_model(qs.model, qs.values("pk"))
    logs = AsKoImportLogEntry.objects.filter(asko_link__in=asko_links)
    print(
        "(unlinking %d AsKoImportLogEntries)" % (logs.count(),),
        end=" ",
        flush=True,
    )
    logs.update(asko_link=None)
    print("(%d AsKoLinks)" % (asko_links.count(),), end=" ", flush=True)
    asko_links.delete()
    print("(%d objects)" % (qs.count(),), end=" ", flush=True)
    qs.delete()
    print("Done.")


def _import_data(directory=None, ignore_errors=False, skip_imported=False):
    directory = directory or ""

    def import_model(fn: str, sc: Type[serializers.ModelSerializer]) -> None:
        if skip_imported and _is_imported(sc.Meta.model):
            return

        with transaction.atomic():
            with log_context(model=sc.Meta.model):
                _import_model(directory, fn, sc, ignore_errors)

                if sc == ApplicantSerializer:
                    _set_applicants_counts()

        # Set reservation positions after lottery results have been imported
        if sc == LotteryEventResultSerializer:
            with log_context(model=ApartmentReservation):
                with transaction.atomic():
                    _set_hitas_reservation_positions()
                with transaction.atomic():
                    _set_haso_reservation_positions()

    print("Importing data from AsKo...")

    import_model("profile.txt", ProfileSerializer)
    import_model("customer.txt", CustomerSerializer)
    import_model("Application.txt", ApplicationSerializer)
    import_model("Applicant.txt", ApplicantSerializer)
    import_model("ApplicationApartment.txt", ApplicationApartmentSerializer)
    import_model("ApartmentReservation.txt", ApartmentReservationSerializer)
    import_model("ProjectInstallmentTemplate.txt", ProjectInstallmentTemplateSerializer)
    import_model("ApartmentInstallment.txt", ApartmentInstallmentSerializer)
    import_model("LotteryEvent.txt", LotteryEventSerializer)
    import_model("LotteryEventResult.txt", LotteryEventResultSerializer)


def _is_imported(model):
    cnt = model.objects.count()
    if cnt > 0:
        print(f"Skipping import of {model.__name__} ({cnt} existing objects)")
        return True
    return False


def _import_model(
    directory: str,
    filename: str,
    serializer_class: Type[serializers.ModelSerializer],
    ignore_errors: bool = False,
) -> Tuple[int, int]:
    imported = 0
    skipped = 0
    model = serializer_class.Meta.model
    checker = DataIssueChecker(model)
    file_path = os.path.join(directory, filename)
    LOG.info("Importing data from file: %s", filename)

    with open(file_path, mode="r", encoding="utf-8-sig") as csv_file:
        count = sum(1 for _ in csv.DictReader(csv_file, delimiter=";"))
        print(f"[{count} entries]", end="", flush=True)
        csv_file.seek(0)

        reader = csv.DictReader(csv_file, delimiter=";")
        for index, row in enumerate(reader, 1):
            with log_context(model=model, row=row):
                if index % 500 == 0:
                    if index % 5000 == 0:
                        print(f"({index})", end="", flush=True)
                    else:
                        print(".", end="", flush=True)
                row = {k.lower(): v for k, v in row.items() if v != ""}
                eid = int(row["id"])  # External ID (aka AsKo ID) of the row

                issues = checker.check(row)
                if issues:
                    issues.log(LOG)
                    skipped += 1
                    continue

                serializer = serializer_class(data=row)
                try:
                    serializer.is_valid(raise_exception=True)
                    instance = serializer.save()
                except Exception:
                    name = model.__name__
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
        "Imported %d rows (skipped: %d, failed: %d)",
        imported,
        skipped,
        failed,
    )

    return imported, count


def _set_applicants_counts():
    applications = _object_store.get_objects(Application)
    LOG.info("Updating applicants_count for %d applications", applications.count())
    for application in applications.annotate(ac=models.Count("applicants")):
        application_qs = Application.objects.filter(pk=application.pk)
        application_qs.update(applicants_count=application.ac)


def _set_hitas_reservation_positions():
    LOG.info("Setting HITAS reservation positions")

    imported_reservations = _object_store.get_objects(ApartmentReservation)
    reservation_qs = imported_reservations.annotate(
        ler_count=models.Count("application_apartment__lotteryeventresult"),
        ler_position=models.Min(
            "application_apartment__lotteryeventresult__result_position"
        ),
    )

    for apartment_uuid in _object_store.get_hitas_apartment_uuids():
        reservations = reservation_qs.filter(apartment_uuid=apartment_uuid)
        ordered_reservations = sorted(reservations, key=_get_hitas_position)
        _set_reservation_positions(ordered_reservations)

    LOG.info("Done setting HITAS reservation positions")


def _get_hitas_position(reservation):
    count = reservation.ler_count
    if count == 1:  # This is the normal case
        return reservation.ler_position

    # Didn't find a linked LotteryEventResult or found many: Log the
    # issue and raise exception if multiple results were found.
    with log_context_from(reservation):
        if count == 0:
            LOG.warning("No LotteryEventResult found")
            return float("inf")
        else:
            LOG.error("Multiple LotteryEventResults found (%d)", count)
            raise Exception("Many LotteryEventResults for single reservation")


def _set_haso_reservation_positions():
    LOG.info("Setting HASO reservation positions")

    imported_reservations = _object_store.get_objects(ApartmentReservation)

    # Order the reservations by right_of_residence. NOTE: Reservations
    # with right_of_residence=NULL will be ordered last.
    reservation_qs = imported_reservations.order_by("right_of_residence")

    # Check whether this is a re-run of the import, and if so, check
    # whether the previous import was incomplete.
    uuids = _object_store.get_haso_apartment_uuids()
    lottery_events = LotteryEvent.objects.filter(apartment_uuid__in=uuids)
    if lottery_events and lottery_events.count() == uuids.count():  # All done
        LOG.info("All HASO lottery events already exist, skipping")
        return
    elif lottery_events:  # Previous import was incomplete
        LOG.error(
            "Some HASO lottery events already exist, but not all. "
            "(HASO apartment count = %d, LotteryEvent count = %d)",
            uuids.count(),
            lottery_events.count(),
        )
        raise Exception("HASO lottery events already exist")
    else:
        LOG.debug("No HASO lottery events found")

    for apartment_uuid in uuids:
        reservations = reservation_qs.filter(apartment_uuid=apartment_uuid)
        lottery_event = LotteryEvent.objects.create(apartment_uuid=apartment_uuid)
        _set_reservation_positions(reservations, lottery_event=lottery_event)

    LOG.info("Done setting HASO reservation positions")


def _set_reservation_positions(
    reservations: Sequence[ApartmentReservation],
    lottery_event: Optional[LotteryEvent] = None,
):
    selected_lp = _find_selected_list_position(reservations)
    queue_position = 0

    for list_position, reservation in enumerate(reservations, 1):
        if list_position < selected_lp and _is_submitted(reservation):
            # Cancel all submitted reservations before the selected one
            reservation.state = ApartmentReservationState.CANCELED

        not_canceled = reservation.state != ApartmentReservationState.CANCELED
        is_submitted = reservation.state == ApartmentReservationState.SUBMITTED

        if not_canceled:
            queue_position += 1

        if queue_position == 1 and is_submitted:
            with log_context_from(reservation):
                LOG.warning("Updating state from SUBMITTED to RESERVED")
            reservation.state = ApartmentReservationState.RESERVED
        elif queue_position > 1 and not_canceled and not is_submitted:
            with log_context_from(reservation):
                LOG.warning(
                    "Updating state from %s to SUBMITTED",
                    reservation.state,
                )
            reservation.state = ApartmentReservationState.SUBMITTED

        ApartmentReservation.objects.filter(pk=reservation.pk).update(
            state=reservation.state,
            list_position=list_position,
            queue_position=(queue_position if not_canceled else None),
        )
        if reservation.state_change_events.count() != 1:
            with log_context_from(reservation):
                LOG.error(
                    "Unexpected number of state change events: %d",
                    reservation.state_change_events.count(),
                )
            raise Exception("State change event count mismatch")
        reservation.state_change_events.update(
            state=reservation.state,
            comment="Tuotu AsKo:sta",
        )
        if lottery_event:
            LotteryEventResult.objects.create(
                event=lottery_event,
                application_apartment=reservation.application_apartment,
                result_position=list_position,
            )


def _find_selected_list_position(reservations: Sequence[ApartmentReservation]) -> int:
    """
    Find the list position of the (first) selected reservation.

    If there is no selected reservation, return the list position of the
    first submitted reservation or if all reservations are cancelled,
    return 0 (which is not a list position, since they start from 1).
    """
    first_submitted_lp = None
    for list_position, reservation in enumerate(reservations, 1):
        if first_submitted_lp is None and _is_submitted(reservation):
            first_submitted_lp = list_position
        elif _is_selected(reservation):
            return list_position
    return first_submitted_lp or 0


def _is_selected(reservation):
    """
    Return True if the reservation is selected for the apartment.

    The CANCELED and SUBMITTED states are not selected, which leaves
    the other states (RESERVED, RESERVATION_AGREEMENT, OFFERED,
    OFFER_ACCEPTED, OFFER_EXPIRED, ACCEPTED_BY_MUNICIPALITY, SOLD,
    REVIEW) as selected.
    """
    return reservation.state not in {
        ApartmentReservationState.CANCELED,
        ApartmentReservationState.SUBMITTED,
    }


def _is_submitted(reservation):
    return reservation.state == ApartmentReservationState.SUBMITTED


def _validate_imported_data():
    LOG.info("Validating imported data...")

    reservations = _object_store.get_objects(ApartmentReservation)

    LOG.info("Checking that %s", "all apartments have a lottery event...")
    apartment_uuids = reservations.values("apartment_uuid").distinct()
    apartment_uuids_without_lottery = apartment_uuids.exclude(
        apartment_uuid__in=LotteryEvent.objects.values("apartment_uuid")
    ).values_list("apartment_uuid", flat=True)
    for apartment_uuid in apartment_uuids_without_lottery:
        LOG.error("Lottery does not exists for apartment %s", apartment_uuid)

    LOG.info("Checking that %s", "all reservations have an application...")
    for reservation in reservations.filter(application_apartment=None):
        with log_context_from(reservation):
            LOG.error("Reservation does not have an application")

    LOG.info("Checking that %s", "queue position 1 is not submitted...")
    in_bad_state_with_queue_pos_1 = reservations.filter(
        queue_position=1, state=ApartmentReservationState.SUBMITTED
    )
    for reservation in in_bad_state_with_queue_pos_1:
        with log_context_from(reservation):
            LOG.error("Reservation in queue pos 1 is submitted")

    LOG.info("Checking that %s", "other queue positions are submitted...")
    in_bad_state_with_queue_pos_gt_1 = (
        reservations.exclude(queue_position=None)
        .exclude(queue_position=1)
        .exclude(state=ApartmentReservationState.SUBMITTED)
    )
    for reservation in in_bad_state_with_queue_pos_gt_1:
        with log_context_from(reservation):
            LOG.error(
                "Reservation should be SUBMITTED but it is %s in position %s",
                reservation.state,
                reservation.queue_position,
            )

    LOG.info("Checking that %s", "temporary list positions are overridden...")
    has_temporary_list_position = reservations.filter(list_position__gte=10000)
    for reservation in has_temporary_list_position:
        with log_context_from(reservation):
            LOG.error(
                "Reservation has a temporary list position (%s)",
                reservation.list_position,
            )

    LOG.info("Data validation complete.")
