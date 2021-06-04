import pytest
import uuid

from apartment.models import Apartment, Project
from apartment.tests.factories import ApartmentFactory, ProjectFactory


@pytest.mark.django_db
def test_apartment_model():
    """Test apartment model"""
    apartment_uuid = uuid.uuid4()
    ApartmentFactory(identifiers=[apartment_uuid])

    assert Apartment.objects.first().identifiers.first().identifier == str(
        apartment_uuid
    )


@pytest.mark.django_db
def test_project_creation():
    """Test project model"""
    project_uuid = uuid.uuid4()
    apartment_uuid = uuid.uuid4()
    project = ProjectFactory(identifiers=[project_uuid])
    ApartmentFactory(project=project, identifiers=[apartment_uuid])

    assert Project.objects.first().identifiers.first().identifier == str(project_uuid)
    assert Apartment.objects.first().project == project
