import logging
from datetime import date
from django.db import transaction

from apartment.enums import IdentifierSchemaType
from apartment.models import Identifier
from application_form.models import Applicant, Application, ApplicationApartment
from application_form.services.queue import add_application_to_queues
from connections.service.elastic import get_and_update_apartment, get_and_update_project

_logger = logging.getLogger(__name__)


@transaction.atomic
def create_application(application_data: dict) -> Application:
    _logger.debug(
        "Creating a new application with external UUID %s",
        application_data["external_uuid"],
    )
    data = application_data.copy()
    profile = data.pop("profile")
    project_id = data.pop("project_id")
    project = get_and_update_project(project_id)
    Identifier.objects.get_or_create(
        schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
        identifier=project_id,
        defaults={"project": project},
    )
    additional_applicant_data = data.pop("additional_applicant")
    application = Application.objects.create(
        external_uuid=data.pop("external_uuid"),
        applicants_count=2 if additional_applicant_data else 1,
        type=data.pop("type"),
        has_children=data.pop("has_children"),
        right_of_residence=data.pop("right_of_residence"),
        profile=profile,
    )
    Applicant.objects.create(
        first_name=profile.first_name,
        last_name=profile.last_name,
        email=profile.email,
        phone_number=profile.phone_number,
        street_address=profile.street_address,
        city=profile.city,
        postal_code=profile.postal_code,
        age=_calculate_age(profile.date_of_birth),
        date_of_birth=profile.date_of_birth,
        ssn_suffix=application_data["ssn_suffix"],
        contact_language=profile.contact_language,
        is_primary_applicant=True,
        application=application,
    )
    if additional_applicant_data:
        Applicant.objects.create(
            first_name=additional_applicant_data["first_name"],
            last_name=additional_applicant_data["last_name"],
            email=additional_applicant_data["email"],
            phone_number=additional_applicant_data["phone_number"],
            street_address=additional_applicant_data["street_address"],
            city=additional_applicant_data["city"],
            postal_code=additional_applicant_data["postal_code"],
            age=_calculate_age(additional_applicant_data["date_of_birth"]),
            date_of_birth=additional_applicant_data["date_of_birth"],
            ssn_suffix=additional_applicant_data["ssn_suffix"],
            application=application,
        )
    apartment_data = data.pop("apartments")
    for apartment_item in apartment_data:
        apartment = get_and_update_apartment(apartment_item["identifier"])
        ApplicationApartment.objects.create(
            application=application,
            apartment=apartment,
            priority_number=apartment_item["priority"],
        )
        Identifier.objects.get_or_create(
            schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
            identifier=apartment_item["identifier"],
            defaults={"apartment": apartment},
        )
    _logger.debug(
        "Application created with external UUID %s", application_data["external_uuid"]
    )
    add_application_to_queues(application)
    return application


def _calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
