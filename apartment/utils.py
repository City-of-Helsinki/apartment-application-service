from apartment.enums import ApartmentState
from application_form.models import ApartmentReservation


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


def get_apartment_state_from_reserved_reservations(reserved_reservations):
    reservation_list = list(reserved_reservations)
    if len(reservation_list) == 0:
        return ApartmentState.FREE.value
    elif len(reservation_list) > 1:
        return ApartmentState.REVIEW.value

    return ApartmentState.get_from_reserved_reservation_state(
        reservation_list[0].state
    ).value
