from apartment.elastic.queries import get_apartment
from apartment.enums import ApartmentState, OwnershipType
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation
from connections.enums import ApartmentStateOfSale


def get_apartment_state_from_apartment_uuid(apartment_uuid):
    try:
        reserved_reservation = ApartmentReservation.objects.reserved().get(
            apartment_uuid=apartment_uuid
        )
    except ApartmentReservation.DoesNotExist:
        return ApartmentState.FREE.value
    except ApartmentReservation.MultipleObjectsReturned:
        return ApartmentState.REVIEW.value

    return ApartmentState.get_from_reserved_reservation_state(
        reserved_reservation.state
    ).value


def get_apartment_state_of_sale_from_event(event):
    """
    If there is a reservation marked as Sold in Sales UI, the apartment state of sale
    should be also changed to SOLD
    If the apartment has no reservations in the sales tool it should show as
    vacant (vapaa) on the Drupal site
    If it has any reservations - regardless the status of reservations -
    the apartment should show as RESERVED (varattu) or RESERVED_HASO (käsittelyssä)
    depending on the apartment type
    """
    if event.state == ApartmentReservationState.SOLD:
        return ApartmentStateOfSale.SOLD
    # Should only check for `FREE` state if
    # the latest change is a reservation cancellation
    if event.state == ApartmentReservationState.CANCELED:
        if (
            ApartmentReservation.objects.active()
            .filter(apartment_uuid=event.reservation.apartment_uuid)
            .only("id")
            .count()
            == 0
        ):
            return ApartmentStateOfSale.FREE_FOR_RESERVATIONS
        # Edge case when there is already a sold reservation
        if (
            ApartmentReservation.objects.active()
            .filter(
                apartment_uuid=event.reservation.apartment_uuid,
                state=ApartmentReservationState.SOLD,
            )
            .only("id")
            .exists()
        ):
            return ApartmentStateOfSale.SOLD

    apartment_type = get_apartment(
        event.reservation.apartment_uuid, include_project_fields=True
    ).project_ownership_type
    if apartment_type.lower() == OwnershipType.HASO.value:
        return ApartmentStateOfSale.RESERVED_HASO
    else:
        return ApartmentStateOfSale.RESERVED


def get_apartment_state_from_reserved_reservations(reserved_reservations):
    reservation_list = list(reserved_reservations)
    if len(reservation_list) == 0:
        return ApartmentState.FREE.value
    elif len(reservation_list) > 1:
        return ApartmentState.REVIEW.value

    return ApartmentState.get_from_reserved_reservation_state(
        reservation_list[0].state
    ).value
