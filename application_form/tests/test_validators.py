import pytest
from datetime import date
from rest_framework.exceptions import ValidationError

from apartment.tests.factories import ApartmentFactory, ProjectFactory
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
def test_project_applicant_validator(
    api_client, elastic_single_project_with_apartments
):
    """
    Applicants can apply only once to the project.
    """
    project = ProjectFactory()
    apartment = ApartmentFactory(project=project)
    application = ApplicationFactory()
    applicants = ApplicantFactory.create_batch(2, application=application)
    ApplicationApartmentFactory(apartment=apartment, application=application)

    # Both applicant exists
    applicant_list = list()
    for applicant in applicants:
        applicant_list.append((applicant.date_of_birth, applicant.ssn_suffix))
    validator = ProjectApplicantValidator()
    with pytest.raises(ValidationError):
        validator(project.uuid, applicant_list)

    # Single applicant exists
    with pytest.raises(ValidationError):
        validator(project.uuid, applicant_list[1])

    # Applicant not exists
    validator(project.uuid, (date(2000, 2, 29), "TAAAA"))
