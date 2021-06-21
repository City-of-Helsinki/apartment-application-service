import pytest
import uuid

from apartment.models import Apartment
from apartment.tests.factories import ApartmentFactory
from application_form.models import Applicant, Application, ApplicationApartment
from application_form.tests.factories import (
    ApplicationApartmentFactory,
    ApplicationFactory,
    ApplicationWithApplicantsFactory,
)


@pytest.mark.django_db
def test_application_model():
    """Test application model"""
    application_uuid = uuid.uuid4()
    ApplicationFactory(external_uuid=application_uuid)

    assert Application.objects.first().external_uuid == application_uuid


@pytest.mark.django_db
def test_application_with_applicants_model():
    """Test application with applicants model"""
    application_uuid = uuid.uuid4()
    applicants_count = 2

    ApplicationWithApplicantsFactory.create(
        external_uuid=application_uuid,
        applicants_count=applicants_count,
    )

    assert Application.objects.first().external_uuid == application_uuid
    assert Applicant.objects.count() == applicants_count


@pytest.mark.django_db
def test_application_has_apartments_model():
    """Test application_has_apartments model"""
    application = ApplicationWithApplicantsFactory.create()
    apartments = ApartmentFactory.create_batch_with_project(5)
    ApplicationApartmentFactory.create_application_with_apartments(
        application=application, apartments=apartments
    )

    # get the set of applications where all apartments belong, should be one
    apartments_application = set(
        [apartment.application_set.first() for apartment in Apartment.objects.all()]
    )

    assert len(apartments_application) == 1
    assert list(apartments_application)[0].id == application.id
    # check that firs occurance of ApartmenApplication object application's id is same
    # as firstly created application
    assert ApplicationApartment.objects.first().application.id == application.id
    assert list(Application.objects.first().apartments.all()) == apartments
