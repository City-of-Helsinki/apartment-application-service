from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apartment.tests.factories import add_to_store, ApartmentDocumentFactory
from application_form.tests.factories import (
    ApplicantFactory,
    ApplicationApartmentFactory,
    ApplicationFactory,
)
from application_form.validators import ProjectApplicantValidator, SSNSuffixValidator


def test_ssn_suffix_validator_valid_1800s():
    date_of_birth = date(1898, 6, 8)
    validator = SSNSuffixValidator(date_of_birth)
    validator("+0541")


def test_ssn_suffix_validator_valid_1900s():
    date_of_birth = date(1959, 8, 1)
    validator = SSNSuffixValidator(date_of_birth)
    validator("-730V")


def test_ssn_suffix_validator_valid_2000s():
    date_of_birth = date(2000, 8, 18)
    validator = SSNSuffixValidator(date_of_birth)
    validator("A163A")


def test_ssn_suffix_validator_invalid_length():
    date_of_birth = date(1959, 8, 1)
    validator = SSNSuffixValidator(date_of_birth)
    with pytest.raises(ValidationError):
        validator("A163A")


def test_ssn_suffix_validator_invalid_date():
    validator = SSNSuffixValidator(None)  # noqa, deliberate wrong type
    with pytest.raises(ValidationError):
        validator("-730V")


def test_ssn_suffix_validator_invalid_century_sign():
    date_of_birth = date(1959, 8, 1)
    validator = SSNSuffixValidator(date_of_birth)
    with pytest.raises(ValidationError):
        validator("X730V")


def test_ssn_suffix_validator_invalid_individual_number():
    date_of_birth = date(1959, 8, 1)
    validator = SSNSuffixValidator(date_of_birth)
    with pytest.raises(ValidationError):
        validator("-001B")


def test_ssn_suffix_validator_invalid_control_character():
    date_of_birth = date(1959, 8, 1)
    validator = SSNSuffixValidator(date_of_birth)
    with pytest.raises(ValidationError):
        validator("730C")


@pytest.mark.django_db
def test_project_applicant_validator(elasticsearch):
    """
    Applicants can apply only once to the project.

    Uses a HITAS project with can_apply_afterwards=False to ensure the duplicate
    applicant check is not bypassed by the late-apply early-return path.
    """
    apartments = []
    first_apt = ApartmentDocumentFactory(
        project_ownership_type="Hitas",
        project_can_apply_afterwards=False,
        project_application_end_time=timezone.now() + timedelta(days=1),
    )
    apartments.append(first_apt)
    for _ in range(4):
        apartments.append(
            ApartmentDocumentFactory(
                project_uuid=first_apt.project_uuid,
                project_ownership_type="Hitas",
                project_can_apply_afterwards=False,
                project_application_end_time=timezone.now() + timedelta(days=1),
            )
        )
    add_to_store(apartments)
    project_uuid = first_apt.project_uuid
    first_apartment_uuid = apartments[0].uuid

    application = ApplicationFactory()
    applicants = ApplicantFactory.create_batch(2, application=application)
    ApplicationApartmentFactory(
        apartment_uuid=first_apartment_uuid, application=application
    )

    applicant_list = [
        (applicant.date_of_birth, applicant.ssn_suffix) for applicant in applicants
    ]
    validator = ProjectApplicantValidator()

    with pytest.raises(PermissionDenied):
        validator(project_uuid, applicant_list)

    with pytest.raises(PermissionDenied):
        validator(project_uuid, applicant_list[1])

    validator(project_uuid, (date(2000, 2, 29), "TAAAA"))


@pytest.mark.django_db
def test_project_applicant_validator_skips_late_hitas_when_can_apply_afterwards(
    elastic_hitas_project_application_end_time_finished,
):
    """
    Late HITAS applicants skip the duplicate-applicant check when
    project_can_apply_afterwards is True.

    - Existing applicant DOB/SSN does not raise when late apply is allowed
    """
    project_uuid, apartment = elastic_hitas_project_application_end_time_finished

    application = ApplicationFactory()
    applicant = ApplicantFactory(application=application)
    ApplicationApartmentFactory(apartment_uuid=apartment.uuid, application=application)

    validator = ProjectApplicantValidator()
    validator(project_uuid, (applicant.date_of_birth, applicant.ssn_suffix))


@pytest.mark.django_db
def test_project_applicant_validator_enforced_for_late_hitas_when_cannot_apply_afterwards(  # noqa: E501
    elastic_hitas_project_no_late_apply,
):
    """
    Late HITAS applicants are still subject to the duplicate-applicant check when
    project_can_apply_afterwards is False.

    - Existing applicant DOB/SSN raises PermissionDenied
    """
    project_uuid, apartment = elastic_hitas_project_no_late_apply

    application = ApplicationFactory()
    applicant = ApplicantFactory(application=application)
    ApplicationApartmentFactory(apartment_uuid=apartment.uuid, application=application)

    validator = ProjectApplicantValidator()
    with pytest.raises(PermissionDenied):
        validator(project_uuid, (applicant.date_of_birth, applicant.ssn_suffix))
