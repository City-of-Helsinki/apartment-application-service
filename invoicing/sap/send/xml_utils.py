from datetime import date, datetime, timedelta
from typing import Union

from django.conf import settings

from apartment.elastic.queries import get_apartment
from invoicing.enums import InstallmentType
from invoicing.models import ApartmentInstallment


def get_base_line_date_string(due_date: Union[datetime, date]) -> str:
    payment_term = settings.SAP.get("PAYMENT_TERMS")
    if payment_term == "N073":
        result = due_date - timedelta(days=10)
    else:
        raise ValueError("PAYMENT_TERMS '{payment_term}' is not defined.")

    result = result.strftime("%Y%m%d")

    return result


def get_installment_type_text(installment_type: InstallmentType) -> str:  # noqa: C901
    if installment_type is InstallmentType.PAYMENT_1:
        result = "1. erä"
    elif installment_type is InstallmentType.PAYMENT_2:
        result = "2. erä"
    elif installment_type is InstallmentType.PAYMENT_3:
        result = "3. erä"
    elif installment_type is InstallmentType.PAYMENT_4:
        result = "4. erä"
    elif installment_type is InstallmentType.PAYMENT_5:
        result = "5. erä"
    elif installment_type is InstallmentType.PAYMENT_6:
        result = "6. erä"
    elif installment_type is InstallmentType.PAYMENT_7:
        result = "7. erä"
    elif installment_type is InstallmentType.DEPOSIT:
        result = "Vakuusmaksu"
    elif installment_type is InstallmentType.DOWN_PAYMENT:
        result = "Käsiraha"
    elif installment_type is InstallmentType.FOR_INVOICING:
        result = "Laskutettava"
    elif installment_type is InstallmentType.LATE_PAYMENT_INTEREST:
        result = "Viivästyskorko"
    elif installment_type is InstallmentType.REFUND:
        result = "Hyvitys"
    elif installment_type is InstallmentType.REFUND_2:
        result = "Hyvitys 2"
    elif installment_type is InstallmentType.REFUND_3:
        result = "Hyvitys 3"
    elif installment_type is InstallmentType.RESERVATION_FEE:
        result = "Varausmaksu"
    elif installment_type is InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT:
        result = "AO-maksu"
    elif installment_type is InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_2:
        result = "AO-maksu 2"
    elif installment_type is InstallmentType.RIGHT_OF_OCCUPANCY_PAYMENT_3:
        result = "AO-maksu 3"
    else:
        raise ValueError("installment_type '{installment_type}' is not defined.")
    return result


def get_wbs_element(installment: ApartmentInstallment) -> str:
    apartment = get_apartment(
        installment.apartment_reservation.apartment_uuid, include_project_fields=True
    )
    ownership_type = apartment.project_ownership_type.upper()

    wbs_element_settings = settings.SAP["WBS_ELEMENT"]
    ownership_type_code = wbs_element_settings["OWNERSHIP_TYPE_CODE"].get(
        ownership_type
    )
    revenue_type_code = wbs_element_settings["REVENUE_TYPE_CODE"].get(ownership_type)

    if not (ownership_type_code and revenue_type_code):
        raise ValueError(f"Invalid ownership type {ownership_type}")

    prefix = wbs_element_settings["PREFIX"]
    property_number = getattr(apartment, "project_property_number", None)
    if not (isinstance(property_number, str) and len(property_number) == 3):
        raise ValueError(f"Invalid property_number {property_number}")

    return f"{prefix}{ownership_type_code}{property_number}{revenue_type_code}"
