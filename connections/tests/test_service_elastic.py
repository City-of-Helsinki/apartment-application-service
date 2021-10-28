import pytest

from connections.service.elastic import get_and_update_apartment, get_and_update_project
from connections.tests.factories import ApartmentFactory


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
def test_get_apartment():
    elastic_apartment = ApartmentFactory.build_and_save_elastic()
    apartment = get_and_update_apartment(elastic_apartment.uuid)
    assert apartment.uuid == elastic_apartment.uuid


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
def test_get_project():
    elastic_apartment = ApartmentFactory.build_and_save_elastic()
    project = get_and_update_project(elastic_apartment.project_uuid)
    assert project.uuid == elastic_apartment.project_uuid
