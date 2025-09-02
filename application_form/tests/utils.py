import logging
import random
import uuid
from datetime import date
from typing import List, Tuple
from django.utils import timezone
from django.db.models.fields import settings
from apartment.elastic.documents import ApartmentDocument
from apartment.elastic.queries import apartment_query
from elasticsearch_dsl import Search

from connections.enums import ApartmentStateOfSale
from users.models import Profile

_logger = logging.getLogger(__name__)

def get_for_sale_elastic_apartments():
    return apartment_query(
        _language="fi",
        apartment_state_of_sale=ApartmentStateOfSale.FOR_SALE
    )

def get_elastic_apartments_with_application_time_left():
    return [
            apt for apt in get_for_sale_elastic_apartments()
            if timezone.now() <= apt.project_application_end_time
    ]

def get_elastic_apartments_uuids(apartments: List[ApartmentDocument]) -> Tuple[uuid.UUID, List[uuid.UUID]]:
    """Extract project_uuid and uuids from `ApartmentDocument` objects.

    Args:
        apartments (List[ApartmentDocument]): List of `ApartmentDocument` objs

    Returns:
        Tuple[uuid.UUID, List[uuid.UUID]]: `project_uuid` common to all the 
        ApartmentDocuments and list of uuids for each ApartmentDocument
    """
    uuids = []
    project_uuid = None

    for apt in apartments:
        if not project_uuid:
            project_uuid = uuid.UUID(apt.project_uuid)
        if project_uuid == uuid.UUID(apt.project_uuid):
            uuids.append(uuid.UUID(apt.uuid))
    return project_uuid, uuids


def calculate_ssn_suffix(date_of_birth: date) -> str:
    date_string = date_of_birth.strftime("%d%m%y")
    century_sign = "+-A"[date_of_birth.year // 100 - 18]
    individual_number = f"{random.randint(3, 899):03d}"
    index = int(date_string + individual_number) % 31
    control_character = "0123456789ABCDEFHJKLMNPRSTUVWXY"[index]
    ssn_suffix = century_sign + individual_number + control_character
    return ssn_suffix


def assert_profile_match_data(profile: Profile, data: dict):
    for field in (
        "first_name",
        "last_name",
        "email",
        "phone_number",
        "street_address",
        "city",
        "postal_code",
        "contact_language",
        "ssn_suffix",
    ):
        if field in data:
            assert data[field] == str(getattr(profile, field))
