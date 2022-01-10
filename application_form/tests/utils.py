import logging
import random
import uuid
from datetime import date
from elasticsearch_dsl import Search
from typing import List, Tuple

from connections.enums import ApartmentStateOfSale

_logger = logging.getLogger(__name__)


def get_elastic_apartments_uuids() -> Tuple[uuid.UUID, List[uuid.UUID]]:
    s_obj = (
        Search()
        .filter("term", _language__keyword="fi")
        .filter("term", apartment_state_of_sale__keyword=ApartmentStateOfSale.FOR_SALE)
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


def calculate_ssn_suffix(date_of_birth: date) -> str:
    date_string = date_of_birth.strftime("%d%m%y")
    century_sign = "+-A"[date_of_birth.year // 100 - 18]
    individual_number = f"{random.randint(3, 899):03d}"
    index = int(date_string + individual_number) % 31
    control_character = "0123456789ABCDEFHJKLMNPRSTUVWXY"[index]
    ssn_suffix = century_sign + individual_number + control_character
    return ssn_suffix
