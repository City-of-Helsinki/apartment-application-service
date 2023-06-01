import uuid

import pytest

from application_form.models.application import Applicant, Application
from application_form.tests.factories import (
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
