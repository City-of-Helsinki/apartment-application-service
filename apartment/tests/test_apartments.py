import pytest
import uuid

from apartment.models import Apartment, Project
from apartment.tests.factories import ApartmentFactory, ProjectFactory


@pytest.mark.django_db
def test_apartment_model():
    """Test apartment model"""
    apartment_uuid = uuid.uuid4()
    ApartmentFactory(id=apartment_uuid)

    assert Apartment.objects.first().id == apartment_uuid


@pytest.mark.django_db
def test_project_creation():
    """Test project model"""
    project_uuid = uuid.uuid4()
    apartment_uuid = uuid.uuid4()
    project = ProjectFactory(id=project_uuid)
    ApartmentFactory(project=project, id=apartment_uuid)

    assert Project.objects.first().id == project_uuid
    assert Apartment.objects.first().project == project
