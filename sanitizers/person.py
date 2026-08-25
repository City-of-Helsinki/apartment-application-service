"""
Plaintext PII sanitizers for anonymized database dumps.

Functions are discovered by database-sanitizer as ``person.<name>`` →
``sanitize_<name>``.
"""

from __future__ import annotations

import itertools
import random
from datetime import date

from django.contrib.auth.hashers import make_password
from faker import Faker

LOCALDEV_PASSWORD = "localdev"

_faker = Faker("fi_FI")
_email_counter = itertools.count(1)
_username_counter = itertools.count(1)
_reference_counter = itertools.count(1)
_password_hash: str | None = None


def _passthrough_empty(value: str | None) -> str | None | bool:
    """Return True when value should be returned unchanged."""
    return value is None or value == ""


def sanitize_first_name(value: str | None) -> str | None:
    """Replace a first name with a Finnish fake first name."""
    if _passthrough_empty(value):
        return value
    return _faker.first_name()


def sanitize_last_name(value: str | None) -> str | None:
    """Replace a last name with a Finnish fake last name."""
    if _passthrough_empty(value):
        return value
    return _faker.last_name()


def sanitize_email(value: str | None) -> str | None:
    """Replace an email with a unique example.com address."""
    if _passthrough_empty(value):
        return value
    return f"user{next(_email_counter)}@example.com"


def sanitize_username(value: str | None) -> str | None:
    """Replace a username with a unique localdev username."""
    if _passthrough_empty(value):
        return value
    return f"user{next(_username_counter)}"


def sanitize_phone_number(value: str | None) -> str | None:
    """Replace a phone number with a Finnish mobile number."""
    if _passthrough_empty(value):
        return value
    return _faker.phone_number()


def sanitize_street_address(value: str | None) -> str | None:
    """Replace a street address with a Finnish fake address."""
    if _passthrough_empty(value):
        return value
    return _faker.street_address()


def sanitize_city(value: str | None) -> str | None:
    """Replace a city name with a Finnish fake city."""
    if _passthrough_empty(value):
        return value
    return _faker.city()


def sanitize_postal_code(value: str | None) -> str | None:
    """Replace a postal code with a Finnish postcode."""
    if _passthrough_empty(value):
        return value
    return _faker.postcode()


def sanitize_comment(value: str | None) -> str | None:
    """Replace free-text comments with lorem text."""
    if _passthrough_empty(value):
        return value
    return _faker.sentence(nb_words=8)


def sanitize_additional_information(value: str | None) -> str | None:
    """Replace customer additional information with lorem text."""
    if _passthrough_empty(value):
        return value
    return _faker.paragraph(nb_sentences=2)


def sanitize_sender_names(value: str | None) -> str | None:
    """Replace application sender names with a fake full name."""
    if _passthrough_empty(value):
        return value
    return f"{_faker.first_name()} {_faker.last_name()}"


def sanitize_handler_information(value: str | None) -> str | None:
    """Replace handler metadata with a generic localdev string."""
    if _passthrough_empty(value):
        return value
    return "localdev-handler"


def sanitize_account_number(value: str | None) -> str | None:
    """Replace a bank account / IBAN with a fake IBAN."""
    if _passthrough_empty(value):
        return value
    return _faker.iban()


def sanitize_reference_number(value: str | None) -> str | None:
    """Replace a payment reference with a unique synthetic reference."""
    if _passthrough_empty(value):
        return value
    return f"9{next(_reference_counter):019d}"


def sanitize_key_value(value: str | None) -> str | None:
    """Replace user key-value storage contents."""
    if _passthrough_empty(value):
        return value
    return "sanitized"


def sanitize_password(value: str | None) -> str | None:
    """
    Replace a password hash with a hash of the documented localdev password.

    All restored users can log in with password ``localdev``.
    """
    global _password_hash
    if _passthrough_empty(value):
        return value
    if _password_hash is None:
        _password_hash = make_password(LOCALDEV_PASSWORD)
    return _password_hash


def fake_national_identification_number(birthday: date) -> str:
    """
    Build a syntactically valid Finnish personal identity code for ``birthday``.

    Parameters:
        birthday (date): Date of birth used for the identity code prefix.

    Returns:
        hetu (str): Eleven-character identity code.
    """
    birth_string = birthday.strftime("%d%m%y")
    century_sign = "+-A"[birthday.year // 100 - 18]
    individual_number = f"{random.randint(3, 899):03d}"
    index = int(birth_string + individual_number) % 31
    control_character = "0123456789ABCDEFHJKLMNPRSTUVWXY"[index]
    return birth_string + century_sign + individual_number + control_character


def sanitize_hetu(value: str | None) -> str | None:
    """Replace a national identification number with a fake HETU."""
    if _passthrough_empty(value):
        return value
    birthday = _faker.date_of_birth(minimum_age=18, maximum_age=90)
    return fake_national_identification_number(birthday)


def sanitize_ssn_suffix(value: str | None) -> str | None:
    """Replace a HETU suffix (century sign + individual + check) with a fake."""
    if _passthrough_empty(value):
        return value
    birthday = _faker.date_of_birth(minimum_age=18, maximum_age=90)
    return fake_national_identification_number(birthday)[6:]


def sanitize_date_of_birth_text(value: str | None) -> str | None:
    """Replace a plaintext date-of-birth string with a fake ISO date."""
    if _passthrough_empty(value):
        return value
    birthday = _faker.date_of_birth(minimum_age=18, maximum_age=90)
    return birthday.isoformat()


def random_adult_date_of_birth() -> date:
    """Return a random adult date of birth for PGP date sanitizers."""
    return _faker.date_of_birth(minimum_age=18, maximum_age=90)
