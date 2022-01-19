import pytest
from django.core.management import call_command

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
    stress_profile = ProfileFactory(email="TestUser-john.doe@example.com")
    normal_profile = ProfileFactory(email="john.doe@example.com")
    stress_application = ApplicationFactory(profile=stress_profile)
    normal_application = ApplicationFactory(profile=normal_profile)
    ApplicationApartmentFactory(application=stress_application)
    normal_apartment_application = ApplicationApartmentFactory(
        application=normal_application
    )

    assert Profile.objects.count() == 2
    assert Application.objects.count() == 2
    assert ApplicationApartment.objects.count() == 2

    call_command("clean_stress_test_data")

    assert Profile.objects.count() == 1
    assert Profile.objects.filter(pk=normal_profile.id).exists()
    assert Application.objects.count() == 1
    assert Application.objects.filter(pk=normal_application.id).exists()
    assert ApplicationApartment.objects.count() == 1
    assert ApplicationApartment.objects.filter(
        pk=normal_apartment_application.id
    ).exists()
