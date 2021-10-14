import logging
import uuid
from elasticsearch_dsl import Search

from apartment.models import Apartment, Project
from connections.elastic_mapper import map_project_ownership_type
from connections.elastic_models import Apartment as ElasticApartment

_logger = logging.getLogger(__name__)


class InvalidElasticDataError(RuntimeError):
    """Raised if invalid hits were returned from Elasticsearch."""


def get_and_update_apartment(identifier: uuid.UUID) -> Apartment:
    elastic_apartment = _get_elastic_apartment_data(identifier)

    if elastic_apartment is None:
        _logger.error(f"There are no apartments with the apartment UUID {identifier}")
        raise InvalidElasticDataError

    return _create_or_update_apartment(elastic_apartment)


def get_and_update_project(identifier: uuid.UUID) -> Project:
    elastic_project = _get_elastic_project_data(identifier)

    if elastic_project is None:
        _logger.error(f"There are no projects with the project UUID {identifier}")
        raise InvalidElasticDataError

    return _create_or_update_project(elastic_project)


def _create_or_update_apartment(elastic_apartment: ElasticApartment) -> Apartment:
    project = _create_or_update_project(elastic_apartment)
    apartment, _ = Apartment.objects.update_or_create(
        uuid=elastic_apartment.uuid,
        defaults={
            "street_address": elastic_apartment.project_street_address,
            "apartment_number": elastic_apartment.apartment_number,
            "room_count": elastic_apartment.room_count,
            "project": project,
        },
    )
    return apartment


def _create_or_update_project(elastic_project: ElasticApartment) -> Project:
    project, _ = Project.objects.update_or_create(
        uuid=elastic_project.project_uuid,
        defaults={
            "ownership_type": map_project_ownership_type(
                elastic_project.project_ownership_type
            ),
            "street_address": elastic_project.project_street_address,
        },
    )
    return project


def _get_elastic_apartment_data(identifier: uuid.UUID) -> ElasticApartment:
    s = Search().query("match", uuid=identifier)
    s.execute()
    objects = list(s.scan())

    if len(objects) > 1:
        _logger.error(
            f"There was a problem fetching apartment data from Elasticsearch. "
            f"There should be only one apartment with the UUID {identifier}, but "
            f"{len(objects)} apartments were found."
        )
        raise InvalidElasticDataError

    if len(objects) == 1:
        _logger.debug(f"Successfully fetched data for apartment {identifier}")
        return objects[0]

    _logger.debug(
        f"Failed to fetch data for apartment {identifier}. The data not exist."
    )
    return None


def _get_elastic_project_data(identifier: uuid.UUID) -> ElasticApartment:
    s = Search().query("match", project_uuid=identifier)
    s.execute()
    objects = list(s.scan())

    if len(objects) > 0:
        _logger.debug(f"Successfully fetched data for project {identifier}")
        return objects[0]

    _logger.debug(f"Failed to fetch data for project {identifier}. The data not exist.")
    return None
