"""
This module contains functionality for describing objects.
"""

from django.db import models

from apartment.elastic.queries import get_apartment, get_project
from application_form.models.application import (
    Applicant,
    Application,
    ApplicationApartment,
)
from application_form.models.lottery import LotteryEvent, LotteryEventResult
from application_form.models.reservation import ApartmentReservation
from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate

TEMPLATE_BY_MODEL = {
    Applicant: "{first_name} {last_name}",
    Application: "{customer} / {apartments}",
    ApplicationApartment: "{apartment} [Pri{priority_number}] / {customer}",
    ApartmentReservation: (
        "[{state} L{list_position} Q{queue_position}] {apartment} / {customer}"
    ),
    LotteryEvent: "{apartment} Lottery {id} at {timestamp}",
    LotteryEventResult: "{result_position}/{result_count} {appl_apartment}",
    ApartmentInstallment: (
        "{due_date} {reference_number} {value}€ {type} -> {reservation}"
    ),
    ProjectInstallmentTemplate: "{project} / {due_date} {type} {value}{unit}",
}


def get_description(obj: models.Model) -> str:
    model = type(obj)
    template_str = TEMPLATE_BY_MODEL.get(model)
    if template_str is not None:
        values = _get_data(obj, template_str)
        return template_str.format(**values)
    else:
        return str(obj)


def _get_data(obj, template_str=""):
    values = {
        field: (value if value is not None else "-")
        for field, value in vars(obj).items()
    }
    fields = [x.split("}")[0] for x in template_str.split("{") if "}" in x]
    for field in fields:
        value = _get_data_field(field, obj)
        if value is not None:
            values[field] = value
    return values


def _get_data_field(field, obj):
    if field == "apartment":
        return get_apartment_info(obj.apartment_uuid)
    elif field == "appl_apartment":
        return get_description(obj.application_apartment)
    elif field == "apartments":
        appl_apartments = obj.application_apartments
        return ", ".join(
            f"[Pri{x.priority_number}] {get_apartment_info(x.apartment_uuid)}"
            for x in appl_apartments.order_by("priority_number")
        )
    elif field == "reservation":
        reservation = obj.apartment_reservation
        return get_description(reservation)
    elif field in {"state", "type"}:
        return getattr(obj, field).name
    elif field == "customer":
        customer = getattr(obj, "customer", None) or obj.application.customer
        return get_description(customer)
    elif field == "result_count":
        return obj.event.results.count()
    elif field == "project":
        return get_project_info(obj.project_uuid)
    elif field == "unit":
        unit = obj.unit.name
        return {"EURO": "€", "PERCENT": "%"}.get(unit, unit)
    return None


def get_apartment_info(apartment_uuid):
    apartment = get_apartment(apartment_uuid, include_project_fields=True)
    housing_comp = apartment.project_housing_company
    num = apartment.apartment_number
    return f"{housing_comp} {num}"


def get_project_info(project_uuid):
    project = get_project(project_uuid)
    housing_comp = project.project_housing_company
    return f"{housing_comp}"
