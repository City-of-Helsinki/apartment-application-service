import logging
import random
import uuid
from datetime import date, datetime, timedelta
from typing import List, Tuple

from django.urls import reverse
from django.utils import timezone

from apartment.enums import OwnershipType
from apartment.tests.factories import (
    add_to_store,
    ApartmentData,
    ApartmentDocumentFactory,
    get_apartments_from_store,
)
from application_form.enums import ApplicationType
from connections.enums import ApartmentStateOfSale
from users.models import Profile
from users.tests.utils import _create_token

_logger = logging.getLogger(__name__)


def get_for_sale_elastic_apartments():
    return [
        apt
        for apt in get_apartments_from_store()
        if apt._language == "fi"
        and apt.apartment_state_of_sale == ApartmentStateOfSale.FOR_SALE
    ]


def get_elastic_apartments_with_application_time_left():
    return [
        apt
        for apt in get_for_sale_elastic_apartments()
        if timezone.now() <= apt.project_application_end_time
    ]


def get_elastic_apartments_uuids(
    apartments: List[ApartmentData],
) -> Tuple[uuid.UUID, List[uuid.UUID]]:
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


def make_late_haso_apartment(**kwargs):
    """
    Create a single HASO apartment past its application period.

    Parameters:
        **kwargs: Overrides for ApartmentDocumentFactory fields.

    Returns:
        ApartmentDocument: The created apartment document.
    """
    defaults = {
        "project_ownership_type": OwnershipType.HASO.value,
        "project_can_apply_afterwards": True,
        "project_application_end_time": (
            datetime.now().replace(tzinfo=timezone.get_default_timezone())
            - timedelta(days=1)
        ),
        "apartment_state_of_sale": ApartmentStateOfSale.FOR_SALE.value,
    }
    defaults.update(kwargs)
    apt = ApartmentDocumentFactory(**defaults)
    add_to_store([apt])
    return apt


def post_single_apartment_application(
    api_client, profile: Profile, apartment, application_type: ApplicationType
):
    """
    POST a single-apartment application of the given type for the profile.

    Parameters:
        api_client: DRF API client.
        profile (Profile): Profile of the applicant.
        apartment: Apartment document to apply to.
        application_type (ApplicationType): Type of the application.

    Returns:
        tuple: (response, request_data) from the applications endpoint.
    """
    # Imported here: conftest imports this module, so a module-level import
    # would be circular.
    from application_form.tests.conftest import create_application_data

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_create_token(profile)}")
    data = create_application_data(
        profile,
        application_type=application_type,
        apartments=[apartment],
    )
    data["apartments"] = [{"priority": 0, "identifier": str(apartment.uuid)}]
    return (
        api_client.post(
            reverse("application_form:application-list"), data, format="json"
        ),
        data,
    )
