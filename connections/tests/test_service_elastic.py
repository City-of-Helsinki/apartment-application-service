import pytest

from apartment.elastic.utils import get_and_update_apartment, get_and_update_project
from apartment.tests.factories import ApartmentDocumentFactory


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
def test_get_apartment():
    elastic_apartment = ApartmentDocumentFactory()
    apartment = get_and_update_apartment(elastic_apartment.uuid)
    assert apartment.uuid == elastic_apartment.uuid


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
def test_get_project():
    elastic_apartment = ApartmentDocumentFactory()
    project = get_and_update_project(elastic_apartment.project_uuid)
    assert project.uuid == elastic_apartment.project_uuid
