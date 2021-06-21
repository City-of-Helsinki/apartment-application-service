from datetime import date
from rest_framework.exceptions import ValidationError


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
