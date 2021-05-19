import pytest
import uuid

from apartment.tests.factories import ApartmentFactory, ProjectFactory


@pytest.mark.django_db
def test_apartment_model():
    """Test apartment model"""
    apartment_uuid = uuid.uuid4()
    apartment = ApartmentFactory(id=apartment_uuid)

    assert apartment.id == apartment_uuid


@pytest.mark.django_db
def test_project_creation():
    """Test project model"""
    project_uuid = uuid.uuid4()
    apartment_uuid = uuid.uuid4()
    project = ProjectFactory(id=project_uuid)
    apartment = ApartmentFactory(project=project, id=apartment_uuid)

    assert project.id == project_uuid
    assert apartment.project == project
    assert apartment.project.id == project_uuid
