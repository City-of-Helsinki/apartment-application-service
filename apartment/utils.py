from apartment.enums import ApartmentState
from application_form.models import ApartmentReservation


def get_apartment_state(apartment_uuid):
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
