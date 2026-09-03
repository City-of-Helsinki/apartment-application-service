"""
Tests for anonymized production dump configuration and sanitizers.

- check_sanitizerconfig covers every Django model column
- Plaintext sanitizers replace PII and preserve null/empty
- PGP sanitizers replace ciphertext with decryptable fakes
- Unique fields stay unique across many calls
- Missing config fields fail the sync check
- Type-based auto-assignment covers user-input fields
- Named exclusions and structural skips stay unsanitized
- Integration: sanitized dump must not contain original PII
"""

import shutil
import subprocess
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from sanitized_dump.config import Configuration
from sanitized_dump.utils.db import db_setting_to_db_string

from sanitizers import person, pgp, types
from sanitizers.config import build_configuration, build_sanitizer_strategy
from users.tests.factories import ProfileFactory

BASE_DIR = Path(settings.BASE_DIR)
CONFIG_PATH = BASE_DIR / ".sanitizerconfig"


def _strategy():
    """Build strategy dict from models for assignment assertions."""
    return build_sanitizer_strategy()


def test_sanitizerconfig_is_in_sync_with_models():
    """
    - Loads committed .sanitizerconfig
    - Asserts every model column is listed (check_sanitizerconfig equivalent)
    """
    conf = Configuration.from_standard_config_file()
    assert conf.in_sync_with_models, conf.diff_with_models


def test_check_sanitizerconfig_command_succeeds(capsys):
    """
    - Runs manage.py check_sanitizerconfig
    - Expects success exit and sync message on stdout
    """
    call_command("check_sanitizerconfig")
    captured = capsys.readouterr()
    assert "IN SYNC" in captured.out


def test_check_sanitizerconfig_fails_when_field_missing():
    """
    - Builds config from models then drops one column
    - Expects diff_with_models to report the missing field
    """
    conf = Configuration.from_models()
    # Proxy models may leave users_user empty; use a known table.
    profile_strategy = conf.strategy.get("users_profile")
    assert profile_strategy is not None
    assert "email" in profile_strategy
    del profile_strategy["email"]
    assert "email" in conf.diff_with_models.get("users_profile", set())


@pytest.mark.parametrize(
    "sanitizer,sample",
    [
        (person.sanitize_first_name, "Maija"),
        (person.sanitize_last_name, "Meikäläinen"),
        (person.sanitize_email, "real.person@hel.fi"),
        (person.sanitize_phone_number, "+358401234567"),
        (person.sanitize_street_address, "Mannerheimintie 1"),
        (person.sanitize_city, "Helsinki"),
        (person.sanitize_postal_code, "00100"),
        (person.sanitize_comment, "Customer called about apartment"),
        (person.sanitize_additional_information, "Has twin children"),
        (person.sanitize_sender_names, "Maija Meikäläinen"),
        (person.sanitize_handler_information, "Handler X"),
        (person.sanitize_account_number, "FI2112345600000785"),
        (person.sanitize_reference_number, "12345678901234567890"),
        (person.sanitize_key_value, "secret-preference"),
        (person.sanitize_password, "pbkdf2_sha256$legacy$hash"),
        (person.sanitize_username, "maija.meikalainen"),
        (person.sanitize_hetu, "010190-123A"),
        (person.sanitize_ssn_suffix, "-123A"),
        (person.sanitize_date_of_birth_text, "1990-01-01"),
    ],
)
def test_plaintext_sanitizers_replace_values(sanitizer, sample):
    """
    - Passes a realistic PII sample to each sanitizer
    - Expects a non-empty different value of the same Python type (str)
    """
    result = sanitizer(sample)
    assert result is not None
    assert isinstance(result, str)
    assert result != sample
    assert result != ""


@pytest.mark.parametrize(
    "sanitizer",
    [
        person.sanitize_first_name,
        person.sanitize_email,
        person.sanitize_phone_number,
        person.sanitize_password,
        person.sanitize_hetu,
        pgp.sanitize_pgp_text,
        pgp.sanitize_pgp_date,
        pgp.sanitize_pgp_ssn_suffix,
        pgp.sanitize_pgp_hetu,
        pgp.sanitize_pgp_handler,
    ],
)
def test_sanitizers_passthrough_null_and_empty(sanitizer):
    """
    - Null and empty inputs are returned unchanged
    """
    assert sanitizer(None) is None
    assert sanitizer("") == ""


def test_unique_usernames_and_emails():
    """
    - Generates many usernames and emails
    - Expects all values unique
    """
    usernames = {person.sanitize_username(f"user{i}") for i in range(50)}
    emails = {person.sanitize_email(f"user{i}@hel.fi") for i in range(50)}
    assert len(usernames) == 50
    assert len(emails) == 50


def test_unique_reference_numbers():
    """
    - Generates many payment reference numbers
    - Expects all values unique
    """
    refs = {person.sanitize_reference_number(str(i)) for i in range(50)}
    assert len(refs) == 50


def test_password_sanitizer_returns_usable_hash():
    """
    - sanitize_password returns a Django-compatible hash
    - Hash verifies against the documented localdev password
    """
    from django.contrib.auth.hashers import check_password

    hashed = person.sanitize_password("anything")
    assert check_password(person.LOCALDEV_PASSWORD, hashed)


def test_hetu_sanitizer_returns_valid_format():
    """
    - sanitize_hetu returns an 11-character Finnish identity code shape
    """
    hetu = person.sanitize_hetu("010190-123A")
    assert len(hetu) == 11
    assert hetu[6] in "+-A"


@pytest.mark.django_db
def test_pgp_text_sanitizer_replaces_ciphertext_and_is_decryptable():
    """
    - Encrypts a known string with the dump public key to simulate COPY input
    - sanitize_pgp_text returns different COPY hex bytea
    - Decrypting with the dump/test private key yields fake plaintext
    """
    original_plain = "Salainen handler"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgp_pub_encrypt(%s, dearmor(%s))",
            [original_plain, settings.DUMP_PUBLIC_PGP_KEY],
        )
        original_cipher = bytes(cursor.fetchone()[0])
    original_copy = "\\x" + original_cipher.hex()

    sanitized_copy = pgp.sanitize_pgp_text(original_copy)
    assert sanitized_copy != original_copy
    assert sanitized_copy.startswith("\\x")

    sanitized_bytes = bytes.fromhex(sanitized_copy[2:])
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgp_pub_decrypt(%s, dearmor(%s))",
            [sanitized_bytes, settings.PRIVATE_PGP_KEY],
        )
        decrypted = cursor.fetchone()[0]
    assert decrypted != original_plain
    assert isinstance(decrypted, str)
    assert len(decrypted) > 0


@pytest.mark.django_db
def test_pgp_hetu_and_date_sanitizers_round_trip():
    """
    - sanitize_pgp_hetu / sanitize_pgp_date produce decryptable fakes
    """
    hetu_copy = pgp.sanitize_pgp_hetu("\\x00")
    date_copy = pgp.sanitize_pgp_date("\\x00")
    assert hetu_copy.startswith("\\x")
    assert date_copy.startswith("\\x")

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pgp_pub_decrypt(%s, dearmor(%s))",
            [bytes.fromhex(hetu_copy[2:]), settings.PRIVATE_PGP_KEY],
        )
        hetu = cursor.fetchone()[0]
        cursor.execute(
            "SELECT pgp_pub_decrypt(%s, dearmor(%s))",
            [bytes.fromhex(date_copy[2:]), settings.PRIVATE_PGP_KEY],
        )
        dob = cursor.fetchone()[0]
    assert len(hetu) == 11
    # Date may be returned as date or string depending on cast
    assert str(dob)


@pytest.mark.django_db
def test_exclude_table_data_tables_are_configured():
    """
    - Sensitive log/session/auth tables are listed for pg_dump --exclude-table-data
    """
    with CONFIG_PATH.open() as handle:
        data = yaml.safe_load(handle)
    excluded = data["config"]["extra_parameters"]["pg_dump"]
    required = [
        "public.django_session",
        "public.django_admin_log",
        "public.audit_log_auditlog",
        "public.resilient_logger_resilientlogentry",
        "public.asko_import_askoimportlogentry",
        "public.social_auth_usersocialauth",
    ]
    for table in required:
        assert any(table in param for param in excluded), table


@pytest.mark.django_db
@pytest.mark.skipif(not shutil.which("pg_dump"), reason="pg_dump not installed")
def test_sanitized_dump_does_not_contain_original_pii():
    """
    - Creates a profile with distinctive PII
    - Runs database-sanitizer against the test database
    - Asserts original name/email/HETU are absent from dump SQL
    """
    distinctive_first = "ZxqwvUniqueFirst"
    distinctive_email = "zxqwv.unique@helsinki-test.example"
    distinctive_hetu = "010190-999X"
    ProfileFactory(
        first_name=distinctive_first,
        email=distinctive_email,
        national_identification_number=distinctive_hetu,
        date_of_birth=date(1990, 1, 1),
    )

    db_url = db_setting_to_db_string(settings.DATABASES)

    process = subprocess.run(
        ["database-sanitizer", "-c", str(CONFIG_PATH), db_url],
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
        check=False,
    )
    assert process.returncode == 0, process.stderr
    dump = process.stdout
    assert distinctive_first not in dump
    assert distinctive_email not in dump
    assert distinctive_hetu not in dump
    assert "COPY" in dump


@pytest.mark.django_db
def test_type_based_assignment_for_user_input_fields():
    """
    - Char/Text/Date/DateTime/Decimal/Integer fields on first-party models
      get matching types.* sanitizers when no PII override exists
    """
    strategy = _strategy()
    assert strategy["application_form_application"]["process_number"] == "types.char"
    assert strategy["apartment_projectextradata"]["offer_message_intro"] == "types.text"
    assert strategy["customer_customer"]["last_contact_date"] == "types.date"
    assert (
        strategy["invoicing_apartmentinstallment"]["added_to_be_sent_to_sap_at"]
        == "types.datetime"
    )
    assert strategy["invoicing_apartmentinstallment"]["value"] == "types.decimal"
    assert strategy["invoicing_payment"]["amount"] == "types.decimal"
    assert strategy["application_form_applicant"]["age"] == "types.integer"
    assert (
        strategy["application_form_application"]["applicants_count"] == "types.integer"
    )
    assert (
        strategy["application_form_apartmentreservation"]["list_position"]
        == "types.integer"
    )
    assert (
        strategy["application_form_lotteryeventresult"]["result_position"]
        == "types.integer"
    )
    assert strategy["cost_index_costindex"]["value"] == "types.decimal"
    assert strategy["cost_index_costindex"]["valid_from"] == "types.date"


@pytest.mark.django_db
def test_named_exclusions_stay_null():
    """
    - ApartmentReservation.queue_position stays null
    - right_of_residence on Application, ApartmentReservation, Customer stays null
    - queue_position_before_cancelation is still type-sanitized
    """
    strategy = _strategy()
    reservation = strategy["application_form_apartmentreservation"]
    assert reservation["queue_position"] is None
    assert reservation["right_of_residence"] is None
    assert reservation["queue_position_before_cancelation"] == "types.integer"
    assert strategy["application_form_application"]["right_of_residence"] is None
    assert strategy["customer_customer"]["right_of_residence"] is None


@pytest.mark.django_db
def test_structural_skips_stay_null():
    """
    - Primary keys, foreign keys, EnumField, choice fields, auto timestamps stay null
    """
    strategy = _strategy()
    reservation = strategy["application_form_apartmentreservation"]
    assert reservation["id"] is None
    assert reservation["customer_id"] is None
    assert reservation["application_apartment_id"] is None
    assert reservation["state"] is None
    assert strategy["application_form_applicant"]["contact_language"] is None
    assert strategy["application_form_applicant"]["created_at"] is None
    assert strategy["application_form_applicant"]["updated_at"] is None
    assert strategy["application_form_offer"]["created_at"] is None
    assert strategy["users_profile"]["contact_language"] is None


@pytest.mark.django_db
def test_pii_overrides_win_over_type_defaults():
    """
    - Explicit PII mappings override type-based defaults
    """
    strategy = _strategy()
    assert strategy["users_profile"]["email"] == "person.email"
    assert strategy["users_profile"]["date_of_birth"] == "pgp.pgp_date"
    assert strategy["users_profile"]["national_identification_number"] == "pgp.pgp_hetu"
    assert strategy["application_form_applicant"]["first_name"] == "person.first_name"
    assert (
        strategy["application_form_apartmentreservation"]["handler"]
        == "pgp.pgp_handler"
    )
    assert strategy["customer_customer"]["additional_information"] == (
        "person.additional_information"
    )


@pytest.mark.django_db
def test_pgp_fields_without_pii_get_pgp_sanitizers():
    """
    - Encrypted boolean/char fields without a named PII entry use pgp sanitizers
      rather than plaintext types.*
    """
    strategy = _strategy()
    reservation = strategy["application_form_apartmentreservation"]
    # Encrypted booleans are PGP fields; they must not get types.integer/char
    assert reservation["has_children"] == "pgp.pgp_text"
    assert reservation["is_age_over_55"] == "pgp.pgp_text"


@pytest.mark.django_db
def test_third_party_and_operational_apps_not_auto_assigned():
    """
    - asko_import / connections / auth columns stay null (no type auto-assign)
    """
    strategy = _strategy()
    assert strategy["asko_import_askolink"]["asko_id"] is None
    assert strategy["asko_import_askoimportlogentry"]["message"] is None
    assert strategy["connections_mappedapartment"]["last_mapped_to_etuovi"] is None
    assert strategy["auth_group"]["name"] is None
    assert strategy["django_session"]["session_data"] is None


@pytest.mark.parametrize(
    "sanitizer,sample,expected_type",
    [
        (types.sanitize_char, "process-123", str),
        (types.sanitize_text, "Long free text about apartment", str),
        (types.sanitize_date, "2024-06-15", str),
        (types.sanitize_datetime, "2024-06-15 12:00:00+00", str),
        (types.sanitize_integer, "42", str),
        (types.sanitize_decimal, "1234.56", str),
        (types.sanitize_float, "3.14", str),
    ],
)
def test_type_sanitizers_replace_values(sanitizer, sample, expected_type):
    """
    - Generic type sanitizers replace non-empty values with dump-compatible strings
    """
    result = sanitizer(sample)
    assert result is not None
    assert isinstance(result, expected_type)
    assert result != sample
    assert result != ""


@pytest.mark.parametrize(
    "sanitizer",
    [
        types.sanitize_char,
        types.sanitize_text,
        types.sanitize_date,
        types.sanitize_datetime,
        types.sanitize_integer,
        types.sanitize_decimal,
        types.sanitize_float,
    ],
)
def test_type_sanitizers_passthrough_null_and_empty(sanitizer):
    """
    - Null and empty inputs are returned unchanged for type sanitizers
    """
    assert sanitizer(None) is None
    assert sanitizer("") == ""


def test_type_sanitizers_produce_unique_values():
    """
    - Integer/date/char type sanitizers stay unique across many calls
    """
    integers = {types.sanitize_integer(str(i)) for i in range(50)}
    dates = {types.sanitize_date(f"2020-01-{(i % 28) + 1:02d}") for i in range(50)}
    chars = {types.sanitize_char(f"value-{i}") for i in range(50)}
    assert len(integers) == 50
    assert len(dates) == 50
    assert len(chars) == 50


def test_type_sanitizer_outputs_are_parseable():
    """
    - Date/datetime/decimal/integer outputs parse to expected Python types
    """
    assert date.fromisoformat(types.sanitize_date("1990-01-01"))
    assert datetime.fromisoformat(types.sanitize_datetime("2020-01-01 00:00:00"))
    assert Decimal(types.sanitize_decimal("10.00"))
    assert int(types.sanitize_integer("7"))
    assert float(types.sanitize_float("1.5"))


@pytest.mark.django_db
def test_committed_sanitizerconfig_matches_generator():
    """
    - Committed .sanitizerconfig strategy matches build_configuration() output
    """
    generated = build_configuration()
    with CONFIG_PATH.open() as handle:
        committed = yaml.safe_load(handle)
    assert committed["strategy"] == generated["strategy"]
    assert (
        committed["config"]["extra_parameters"]
        == generated["config"]["extra_parameters"]
    )
