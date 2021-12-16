import logging
import uuid
from elasticsearch_dsl import Search
from typing import List, Tuple
from unittest.mock import Mock

from apartment.tests.factories import IdentifierFactory
from application_form.api.serializers import ApplicationSerializer
from application_form.enums import ApplicationType
from application_form.tests.factories import ApplicantFactory, calculate_ssn_suffix
from connections.enums import ApartmentStateOfSale

_logger = logging.getLogger(__name__)


def get_elastic_apartments_uuids() -> Tuple[uuid.UUID, List[uuid.UUID]]:
    s_obj = (
        Search()
        .query("match", _language="fi")
        .query("match", apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE)
    )
    s_obj.execute()
    scan = s_obj.scan()
    uuids = []
    project_uuid = None
    for hit in scan:
        if not project_uuid:
            project_uuid = uuid.UUID(hit.project_uuid)
        if project_uuid == uuid.UUID(hit.project_uuid):
            uuids.append(uuid.UUID(hit.uuid))
    return project_uuid, uuids


def create_application_data(
    profile, application_type=ApplicationType.HASO, num_applicants=2
):
    # Build apartments by creating identifiers
    project_uuid, apartment_uuids = get_elastic_apartments_uuids()
    apartments = IdentifierFactory.build_batch_for_att_schema(5, apartment_uuids)
    apartments_data = [
        {"priority": index, "identifier": apartment.identifier}
        for index, apartment in enumerate(apartments)
    ]
    right_of_residence = 123456 if application_type == ApplicationType.HASO else None

    # Build application request data
    application_data = {
        "application_uuid": str(uuid.uuid4()),
        "application_type": application_type.value,
        "ssn_suffix": calculate_ssn_suffix(profile),
        "has_children": True,
        "right_of_residence": right_of_residence,
        "additional_applicant": None,
        "project_id": str(project_uuid),
        "apartments": apartments_data,
    }
    # Add a second applicant if needed
    if num_applicants == 2:
        applicant = ApplicantFactory.build()
        application_data["additional_applicant"] = {
            "first_name": applicant.first_name,
            "last_name": applicant.last_name,
            "email": applicant.email,
            "street_address": applicant.street_address,
            "postal_code": applicant.postal_code,
            "city": applicant.city,
            "phone_number": applicant.phone_number,
            "date_of_birth": "2000-05-14",
            "ssn_suffix": "A757F",
        }
    return application_data


def create_validated_application_data(
    profile, application_type=ApplicationType.HASO, num_applicants=2
):
    application_data = create_application_data(
        profile, application_type, num_applicants
    )
    serializer = ApplicationSerializer(
        data=application_data,
        context={"request": Mock(user=profile.user)},
    )
    serializer.is_valid(raise_exception=True)
    return {**serializer.validated_data, "profile": profile}
