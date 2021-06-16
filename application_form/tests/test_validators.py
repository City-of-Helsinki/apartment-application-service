import pytest
from datetime import date
from rest_framework.exceptions import ValidationError

from application_form.validators import SSNSuffixValidator


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
