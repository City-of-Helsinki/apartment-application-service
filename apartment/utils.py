from datetime import datetime
from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import get_apartment
from apartment.enums import ApartmentState, OwnershipType
from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation
from connections.enums import ApartmentStateOfSale
from connections.utils import clean_html_tags_from_text
from django.conf import settings


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


def form_description_with_link(elastic_apartment: ApartmentDocument):
    """
    Fetch link to project and add it to the start of description.
    Fetch link to the apartment itself and add it to the end of the description.
    Replace <br> and </p> with line breaks.
    """

    optional_text = "Tarkemman kohde-esittelyn sekä varaustilanteen löydät täältä:"
    main_text = getattr(elastic_apartment, "project_description", None)

    if settings.DEBUG:
        main_text = f"[debug] Päivitetty {datetime.now().isoformat()}\n\n{main_text}"

    if main_text:
        main_text = clean_html_tags_from_text(main_text)
    project_link = getattr(elastic_apartment, "project_url", None)
    apartment_link = getattr(elastic_apartment, "url", None)

    project_link_text = f"Tarkemman kohde-esittelyn sekä varaustilanteen löydät täältä:\n{project_link}"  # noqa: E501
    if project_link:
        return "\n\n".join(filter(None, [project_link_text, main_text, apartment_link]))

    if apartment_link:
        return "\n\n".join(filter(None, [main_text, apartment_link]))

    if main_text and project_link:
        return f"{optional_text}\n{project_link}\n\n{main_text}\n\n{apartment_link}"

    if not main_text and project_link:
        return f"{optional_text}\n"

    if not main_text and project_link:
        return "\n".join(filter(None, [optional_text, project_link]))
    if main_text or project_link:
        return "\n\n".join(filter(None, [main_text, project_link]))

    pass
