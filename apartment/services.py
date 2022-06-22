from datetime import date
from decimal import Decimal
from typing import Optional, Union

from apartment.elastic.queries import get_apartment
from apartment.models import ProjectExtraData
from application_form.models import ApartmentReservation, Offer


def get_offer_message_subject_and_body(
    reservation: ApartmentReservation, valid_until=Optional[date]
) -> (str, str):
    apartment = get_apartment(reservation.apartment_uuid, include_project_fields=True)

    if not valid_until:
        try:
            valid_until = reservation.offer.valid_until
        except Offer.DoesNotExist:
            pass

    try:
        project_data = ProjectExtraData.objects.get(project_uuid=apartment.project_uuid)
        intro = (
            project_data.offer_message_intro.replace("\r\n", "\n").rstrip("\n") + "\n"
        )
        content = (
            project_data.offer_message_content.replace("\r\n", "\n").rstrip("\n") + "\n"
        )
    except ProjectExtraData.DoesNotExist:
        intro = ""
        content = ""

    dynamic = _get_offer_message_body_dynamic_part(
        reservation, apartment, valid_until=valid_until
    )

    body = "\n".join([part for part in (intro, dynamic, content) if part]).replace(
        "\n", "\r\n"
    )
    subject = (
        f"Tarjous {apartment.project_housing_company} {apartment.apartment_number}"
    )

    return subject, body


def _get_offer_message_body_dynamic_part(
    reservation: ApartmentReservation, apartment, valid_until=Optional[date]
) -> str:
    common_part = f"""Huoneisto: {apartment.apartment_number}
Huoneistotyyppi: {apartment.apartment_structure}
Pinta-ala: {apartment.living_area}
Kerros: {apartment.floor}. krs
"""
    ownership_type = apartment.project_ownership_type.lower()
    if ownership_type in ("hitas", "puolihitas"):
        ownership_specific_part = _get_hitas_dynamic_part(reservation, apartment)
    elif ownership_type == "haso":
        ownership_specific_part = _get_haso_dynamic_part(reservation, apartment)
    else:
        raise ValueError(f'Unknown project ownership_type "{ownership_type}"')

    valid_until_part = (
        f"Tarjouksen viimeinen voimassaolopäivä: {_get_date_str(valid_until)}\n"
    )

    return common_part + "\n" + ownership_specific_part + "\n" + valid_until_part


def _get_hitas_dynamic_part(reservation: ApartmentReservation, apartment) -> str:
    return f"""Myyntihinta: {_get_price_str(apartment.sales_price)}
Velaton hinta: {_get_price_str(apartment.debt_free_sales_price)}
Alustava vastike: {_get_price_str(apartment.maintenance_fee)}

Lapsiperhe: {_get_bool_str(reservation.customer.has_children)}
"""


def _get_haso_dynamic_part(reservation: ApartmentReservation, apartment) -> str:
    return f"""Alustava asumisoikeusmaksu: {_get_price_str(apartment.right_of_occupancy_payment)}
Alustava käyttövastike: {_get_price_str(apartment.right_of_occupancy_fee)}
Käyttövakuus: {_get_price_str(apartment.right_of_occupancy_deposit)}

Asumisoikeusnumero: {_get_int_str(reservation.customer.right_of_residence)}
Yli 55v: {_get_bool_str(reservation.customer.is_age_over_55)}
Asumisoikeusasunnon vaihtaja: {_get_bool_str(reservation.customer.is_right_of_occupancy_housing_changer)}
"""  # noqa: E501


def _get_price_str(cents: int) -> str:
    return (
        format((Decimal(cents) / 100).quantize(Decimal(".01")), ",")
        .replace(",", " ")
        .replace(".", ",")
    ) + " €"


def _get_bool_str(value: Union[bool, None]) -> str:
    if value is None:
        return "Ei tiedossa"
    return "Kyllä" if value else "Ei"


def _get_int_str(value: Union[int, None]) -> str:
    if value is None:
        return "Ei tiedossa"
    return str(value)


def _get_date_str(value: Union[date, None]) -> str:
    if value is None:
        return "Ei tiedossa"
    return value.strftime("%-d.%-m.%Y")
