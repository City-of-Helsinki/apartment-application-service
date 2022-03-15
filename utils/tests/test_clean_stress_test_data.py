import pytest
from django.core.management import call_command

from application_form.models.application import Application, ApplicationApartment
from application_form.tests.factories import (
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from customer.models import Customer
from customer.tests.factories import CustomerFactory


@pytest.mark.django_db
def test_clean_stress_test_data():
    # Create base data
    stress_customer = CustomerFactory(
        primary_profile__email="TestUser-john.doe@example.com"
    )
    normal_customer = CustomerFactory(primary_profile__email="john.doe@example.com")
    stress_application = ApplicationFactory(customer=stress_customer)
    normal_application = ApplicationFactory(customer=normal_customer)
    ApplicationApartmentFactory(application=stress_application)
    normal_apartment_application = ApplicationApartmentFactory(
        application=normal_application
    )

    assert Customer.objects.count() == 2
    assert Application.objects.count() == 2
    assert ApplicationApartment.objects.count() == 2

    call_command("clean_stress_test_data")

    assert Customer.objects.count() == 1
    assert Customer.objects.filter(pk=normal_customer.id).exists()
    assert Application.objects.count() == 1
    assert Application.objects.filter(pk=normal_application.id).exists()
    assert ApplicationApartment.objects.count() == 1
    assert ApplicationApartment.objects.filter(
        pk=normal_apartment_application.id
    ).exists()
