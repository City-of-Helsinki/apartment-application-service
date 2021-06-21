import logging
from datetime import date
from django.db import transaction
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Hit

from apartment.enums import IdentifierSchemaType
from apartment.models import Apartment, Identifier, Project
from application_form.models import Applicant, Application, ApplicationApartment

_logger = logging.getLogger(__name__)


class InvalidElasticDataError(RuntimeError):
    """Raised if invalid hits were returned from Elasticsearch."""


@transaction.atomic
def create_application(application_data: dict) -> Application:
    _logger.debug(
        "Creating a new application with external UUID %s",
        application_data["external_uuid"],
    )
    data = application_data.copy()
    profile = data.pop("profile")
    project_id = data.pop("project_id")
    project, _ = Project.objects.get_or_create(
        street_address=_get_elastic_project_data(project_id)
    )
    Identifier.objects.get_or_create(
        schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
        identifier=project_id,
        project=project,
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
        first_name=profile.user.first_name,
        last_name=profile.user.last_name,
        email=profile.user.email,
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
        elastic_apartment = _get_elastic_apartment_data(apartment_item["identifier"])
        apartment, _ = Apartment.objects.get_or_create(
            street_address=elastic_apartment.project_street_address,
            apartment_number=elastic_apartment.apartment_number,
            project=project,
        )
        ApplicationApartment.objects.create(
            application=application,
            apartment=apartment,
            priority_number=apartment_item["priority"],
        )
        Identifier.objects.get_or_create(
            schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
            identifier=apartment_item["identifier"],
            apartment=apartment,
        )
    _logger.debug(
        "Application created with external UUID %s", application_data["external_uuid"]
    )
    return application


def _get_elastic_apartment_data(identifier: str) -> Hit:
    s = Search().query("match", uuid=identifier)
    s.execute()
    objects = list(s.scan())

    if len(objects) != 1:
        _logger.error(
            f"There was a problem fetching apartment data from Elasticsearch. "
            f"There should be only one apartment with the UUID {identifier}, but "
            f"{len(objects)} apartments were found."
        )
        raise InvalidElasticDataError

    _logger.debug(f"Successfully fetched data for apartment {identifier}")
    return objects[0]


def _get_elastic_project_data(identifier: str) -> Hit:
    s = Search().query("match", project_uuid=identifier)
    s.execute()
    objects = list(s.scan())

    if len(objects) < 1:
        _logger.error(f"There are no apartments with the project UUID {identifier}")
        raise InvalidElasticDataError

    _logger.debug(f"Successfully fetched data for project {identifier}")
    return objects[0]


def _calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
