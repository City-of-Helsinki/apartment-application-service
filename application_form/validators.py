from datetime import date
from typing import List, Tuple, Union
from uuid import UUID

from rest_framework.exceptions import PermissionDenied, ValidationError

from apartment.elastic.queries import get_apartment, get_apartment_uuids
from application_form import error_codes
from application_form.models import Applicant


class SSNSuffixValidator:
    valid_century_signs = ["+", "-", "A"]

    def __init__(self, date_of_birth: date):
        self.date_of_birth = date_of_birth

    def __call__(self, value: str):
        if not isinstance(self.date_of_birth, date):
            raise ValidationError("cannot validate without date of birth")
        if len(value) != 5:
            raise ValidationError("length is not 5")
        century_sign = value[0]
        individual_number = value[1:4]
        control_character = value[4]
        self._validate_century_sign(century_sign)
        self._validate_individual_number(individual_number)
        self._validate_control_character(control_character, individual_number)

    def _validate_century_sign(self, century_sign: str):
        if century_sign not in self.valid_century_signs:
            raise ValidationError(
                f"century sign must be one of {', '.join(self.valid_century_signs)}"
            )

    def _validate_individual_number(self, individual_number: str):
        if individual_number in ["000", "001"]:
            raise ValidationError("individual number cannot be 001 or 001")

    def _validate_control_character(
        self, control_character: str, individual_number: str
    ):
        try:
            expected = self._calculate_control_character(individual_number)
        except ValueError:
            raise ValidationError("Could not calculate control character.")
        if control_character != expected:
            raise ValidationError(
                f"control character {control_character} "
                f"does not match the calculated {expected}"
            )

    def _calculate_control_character(self, individual_number: str) -> str:
        alphabet = "0123456789ABCDEFHJKLMNPRSTUVWXY"
        number = int(self.date_of_birth.strftime("%d%m%y") + individual_number)
        index = number % len(alphabet)
        return alphabet[index]


class ProjectApplicantValidator:
    def __call__(
        self,
        project_uuid: UUID,
        date_of_birth_and_ssn_suffix: Union[Tuple[date, str], List[Tuple[date, str]]],
    ):
        if isinstance(date_of_birth_and_ssn_suffix, Tuple):
            date_of_birth_and_ssn_suffix = [date_of_birth_and_ssn_suffix]
        if isinstance(date_of_birth_and_ssn_suffix, List):
            date_of_birth_and_ssn_suffix = date_of_birth_and_ssn_suffix.copy()

        if not date_of_birth_and_ssn_suffix:
            return

        apartment_uuids = get_apartment_uuids(project_uuid)
        # We fetch the project's all DOBs and SSN suffixes first and then check those in
        # Python to make sure Postgres won't end up decrypting all applicants in the
        # database, which it seems to prefer and that caused major issues before.
        project_applicants = list(
            Applicant.objects.filter(
                application__application_apartments__apartment_uuid__in=apartment_uuids
            ).values_list("date_of_birth", "ssn_suffix")
        )
        for date_of_birth, ssn_suffix in date_of_birth_and_ssn_suffix:
            if (date_of_birth, ssn_suffix) in project_applicants:
                raise PermissionDenied(
                    detail="Applicant(s) have already applied to project.",
                    code=error_codes.E1001_APPLICANT_HAS_ALREADY_APPLIED,
                )


class ApartmentApplicationValidator:
    def __call__(
        self,
        apartment_uuid: UUID,
    ):
        apartment = get_apartment(apartment_uuid, include_project_fields=True)
        unpublished = "unpublished" if not apartment.apartment_published else ""
        if (
            not apartment.apartment_published
            or apartment.apartment_state_of_sale.upper() == "SOLD"
        ):
            raise ValidationError(
                f"Can't create application for {unpublished} apartment {apartment.uuid}"
                f"State of sale {apartment.apartment_state_of_sale}"
            )
