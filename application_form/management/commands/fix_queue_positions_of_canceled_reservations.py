"""
Update queue positions of canceled reservations.

Due to a problem in the system it was possible to create duplicate
applications for the same project and apartments which should not have
been possible.  That situation was fixed by cancelling the duplicates
before the lottery, but the lottery engine was not able to take the
cancelled reservations into account, i.e. ignoring them in the lottery.

This script will fix the queues so that those reservations which were
canceled before the lottery are removed from the queue.  They should
have never been taken into to the lottery anyway, so it's an error that
they have a queue position.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand

from apartment.elastic.queries import get_apartment_project_uuid, get_project
from application_form.services.queue import remove_reservation_from_queue
from asko_import.describer import get_description

from ... import enums
from ...models import ApartmentReservation, LotteryEvent

canceled = enums.ApartmentReservationState.CANCELED
lower_priority = enums.ApartmentReservationCancellationReason.LOWER_PRIORITY


class Command(BaseCommand):
    help = __doc__.strip().splitlines()[0]

    def handle(self, *args, **options):
        print("Updating queue positions of canceled reservations...")
        projects = list(get_problematic_projects())
        for n, project in enumerate(projects, 1):
            print(f"{n} {project}")

        project_num = input("Select a project to update: ")
        project = projects[int(project_num) - 1]

        lotteries = project.lotteries
        for n, lottery in enumerate(lotteries, 1):
            print(f"{n} {get_description(lottery)}")

        lottery_choice = input("Select a lottery to update (A for all): ")
        if lottery_choice != "A":
            lottery = lotteries[int(lottery_choice) - 1]
            lotteries = [lottery]

        reservations_to_fix = self.print_state_and_get_what_to_fix(lotteries)

        ans = input("Fix the queue positions of reservations marked with X? ")
        if ans.lower() == "y":
            self.fix(reservations_to_fix)
            print("")
            self.print_state_and_get_what_to_fix(lotteries)

    def print_state_and_get_what_to_fix(self, lotteries):
        print("Current state:")
        print("")
        print("X = queue position needs to be fixed")
        print("b = was canceled before lottery")
        print("")
        reservations_to_fix = []
        for lottery in lotteries:
            print(f"{get_description(lottery)}")
            apartment_uuid = lottery.apartment_uuid
            reservations = get_ordered_reservations(apartment_uuid)
            problematic = get_problematic_reservations(apartment_uuid)
            for reservation in reservations:
                needs_fixing = reservation in problematic
                was_canceled_before = was_canceled_before_lottery(reservation)
                prefix1 = "X" if needs_fixing else " "
                prefix2 = "b" if was_canceled_before else " "
                print(f"  - {prefix1}{prefix2} {get_description(reservation)}")
                if needs_fixing:
                    if not was_canceled_before:
                        raise ValueError("Was not canceled before lottery")
                    reservations_to_fix.append(reservation)
        return reservations_to_fix

    def fix(self, reservations_to_fix):
        for reservation in reservations_to_fix:
            print(f"Fixing {get_description(reservation)}...")
            # Refresh reservation from DB to make sure we have the latest
            # value of the queue_position field, since it might have been
            # updated by previous iterations of this loop.
            reservation.refresh_from_db()
            remove_reservation_from_queue(
                reservation,
                comment="Poistettu jonosta, koska oli peruttu ennen arvontaa",
            )
        print("Fixed.")


def was_canceled_before_lottery(reservation):
    if reservation.state == canceled:
        priority_lowering_events = reservation.state_change_events.filter(
            state=canceled,
            cancellation_reason=lower_priority,
        )
        if not priority_lowering_events:
            return True  # Is canceled and was not lowered in priority
    return False


def get_problematic_projects():
    lotteries = get_problematic_lotteries()
    projects_by_uuid = ProjectMap()
    for lottery in lotteries.distinct():
        apartment_uuid = lottery.apartment_uuid
        project_uuid = get_apartment_project_uuid(apartment_uuid).project_uuid
        project = projects_by_uuid[project_uuid]
        project.lotteries.append(lottery)
    return projects_by_uuid.values()


class ProjectMap(defaultdict):
    def __missing__(self, key):
        self[key] = Project(key)
        return self[key]


class Project:
    def __init__(self, project_uuid):
        self.project_uuid = project_uuid
        self.lotteries = []

    def __str__(self):
        project = get_project(self.project_uuid)
        type_name = project.project_ownership_type
        hc_name = project.project_housing_company
        return f"[{type_name}] {hc_name}"


def get_ordered_reservations(apartment_uuid):
    reservations = get_reservations(apartment_uuid)
    return reservations.order_by("list_position")


def get_problematic_lotteries():
    reservations = get_problematic_reservations()
    apartment_uuids = reservations.values("apartment_uuid")
    return LotteryEvent.objects.filter(apartment_uuid__in=apartment_uuids)


def get_problematic_reservations(apartment_uuid=None):
    reservations = get_reservations(apartment_uuid)
    canceled_reservations = reservations.filter(state=canceled)
    with_queue_position = canceled_reservations.exclude(queue_position=None)
    lotterized_apartments = LotteryEvent.objects.values("apartment_uuid")
    return with_queue_position.filter(apartment_uuid__in=lotterized_apartments)


def get_reservations(apartment_uuid=None):
    all_reservations = ApartmentReservation.objects.all()
    if apartment_uuid:
        return all_reservations.filter(apartment_uuid=apartment_uuid)
    else:
        return all_reservations
