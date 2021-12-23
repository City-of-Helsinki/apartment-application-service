import pytest
from django.core.management import call_command

from apartment.models import Apartment, Project
from apartment.tests.factories import ApartmentFactory, ProjectFactory
from application_form.models.application import Application, ApplicationApartment
from application_form.tests.factories import (
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from users.models import Profile
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
def test_clean_stress_test_data():
    # Create base data
    stress_project = ProjectFactory()
    normal_project = ProjectFactory()
    stress_apartment = ApartmentFactory(project=stress_project)
    normal_apartment = ApartmentFactory(project=normal_project)
    stress_profile = ProfileFactory(email="TestUser-john.doe@example.com")
    normal_profile = ProfileFactory(email="john.doe@example.com")
    stress_application = ApplicationFactory(profile=stress_profile)
    normal_application = ApplicationFactory(profile=normal_profile)
    ApplicationApartmentFactory(
        apartment=stress_apartment, application=stress_application
    )
    normal_apartment_application = ApplicationApartmentFactory(
        apartment=normal_apartment, application=normal_application
    )

    assert Project.objects.count() == 2
    assert Apartment.objects.count() == 2
    assert Profile.objects.count() == 2
    assert Application.objects.count() == 2
    assert ApplicationApartment.objects.count() == 2

    call_command("clean_stress_test_data")

    assert Project.objects.count() == 1
    assert Project.objects.filter(pk=normal_project.id).exists()
    assert Apartment.objects.count() == 1
    assert Apartment.objects.filter(pk=normal_apartment.id).exists()
    assert Profile.objects.count() == 1
    assert Profile.objects.filter(pk=normal_profile.id).exists()
    assert Application.objects.count() == 1
    assert Application.objects.filter(pk=normal_application.id).exists()
    assert ApplicationApartment.objects.count() == 1
    assert ApplicationApartment.objects.filter(
        pk=normal_apartment_application.id
    ).exists()
