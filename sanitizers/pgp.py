"""
PGP field sanitizers for anonymized dumps.

Encrypted columns are replaced with new ciphertext produced via read-only
``SELECT pgp_pub_encrypt(...)`` using ``DUMP_PUBLIC_PGP_KEY``. Production rows
are never updated. Values are returned in Postgres COPY hex bytea form
(``\\x`` + hex) so ``database-sanitizer`` can encode them into the dump stream.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from faker import Faker

from sanitizers.person import (
    fake_national_identification_number,
    random_adult_date_of_birth,
)

_faker = Faker("fi_FI")


def _passthrough_empty(value: str | None) -> bool:
    """Return True when value should be returned unchanged."""
    return value is None or value == ""


def _encrypt_for_dump(plaintext: str) -> str:
    """
    Encrypt plaintext with the dump public key and return COPY hex bytea text.

    Parameters:
        plaintext (str): Fake plaintext to encrypt.

    Returns:
        copy_bytea (str): ``\\x``-prefixed hex suitable for encode_copy_value.
    """
    public_key = settings.DUMP_PUBLIC_PGP_KEY
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgp_pub_encrypt(%s, dearmor(%s))",
            [plaintext, public_key],
        )
        ciphertext = cursor.fetchone()[0]
    return "\\x" + bytes(ciphertext).hex()


def sanitize_pgp_text(value: str | None) -> str | None:
    """Replace encrypted text with a fake name encrypted for the dump key."""
    if _passthrough_empty(value):
        return value
    return _encrypt_for_dump(_faker.name())


def sanitize_pgp_bool(value: str | None) -> str | None:
    """
    Replace an encrypted boolean with a random encrypted boolean.

    The plaintext must be castable to Postgres BOOL, since
    BooleanPGPPublicKeyField decrypts with ``::BOOL``.
    """
    if _passthrough_empty(value):
        return value
    return _encrypt_for_dump("true" if _faker.pybool() else "false")


def sanitize_pgp_bool_keep(value: str | None) -> str | None:
    """
    Keep an encrypted boolean's value, re-encrypted for the dump key.

    Used where the value drives business logic (e.g. HITAS lottery) that
    must behave the same on a restored dump. The value is decrypted with
    ``PRIVATE_PGP_KEY`` inside Postgres and never leaves it as plaintext.

    Raises:
        ImproperlyConfigured: When PRIVATE_PGP_KEY is not set.
    """
    if _passthrough_empty(value):
        return value
    private_key = settings.PRIVATE_PGP_KEY
    if not private_key:
        raise ImproperlyConfigured(
            "Set PRIVATE_PGP_KEY to keep encrypted boolean values in the dump."
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgp_pub_encrypt("
            "pgp_pub_decrypt(%s, dearmor(%s))::BOOL::TEXT, dearmor(%s))",
            [bytes.fromhex(value[2:]), private_key, settings.DUMP_PUBLIC_PGP_KEY],
        )
        ciphertext = cursor.fetchone()[0]
    return "\\x" + bytes(ciphertext).hex()


def sanitize_pgp_handler(value: str | None) -> str | None:
    """Replace an encrypted handler name with a fake encrypted name."""
    if _passthrough_empty(value):
        return value
    return _encrypt_for_dump(_faker.name())


def sanitize_pgp_date(value: str | None) -> str | None:
    """Replace an encrypted date of birth with a fake adult DOB."""
    if _passthrough_empty(value):
        return value
    return _encrypt_for_dump(random_adult_date_of_birth().isoformat())


def sanitize_pgp_hetu(value: str | None) -> str | None:
    """Replace an encrypted national identification number with a fake HETU."""
    if _passthrough_empty(value):
        return value
    birthday = random_adult_date_of_birth()
    return _encrypt_for_dump(fake_national_identification_number(birthday))


def sanitize_pgp_ssn_suffix(value: str | None) -> str | None:
    """Replace an encrypted HETU suffix with a fake suffix."""
    if _passthrough_empty(value):
        return value
    birthday = random_adult_date_of_birth()
    return _encrypt_for_dump(fake_national_identification_number(birthday)[6:])
