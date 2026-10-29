"""
Build `.sanitizerconfig` strategy from Django models.

Applies type-based sanitizers for user-input fields on first-party apps,
skips structural fields, applies named exclusions, then overlays explicit
PII mappings.
"""

from __future__ import annotations

from typing import Any, Iterator

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import models
from enumfields import EnumField
from pgcrypto.fields import DatePGPPublicKeyField
from pgcrypto.mixins import PGPPublicKeyFieldMixin
from sanitized_dump.config import Configuration

FIRST_PARTY_APPS = frozenset(
    {
        "apartment",
        "application_form",
        "customer",
        "invoicing",
        "cost_index",
        "users",
    }
)

# Columns that must remain unsanitized even when type heuristics match.
NAMED_EXCLUSIONS = frozenset(
    {
        ("application_form_apartmentreservation", "queue_position"),
        ("application_form_application", "right_of_residence"),
        ("application_form_apartmentreservation", "right_of_residence"),
        ("customer_customer", "right_of_residence"),
        # Links Django applications to Drupal asu_application entities.
        ("application_form_application", "drupal_application_id"),
    }
)

# Sanitizer ids used by several PII columns.
FIRST_NAME = "person.first_name"
LAST_NAME = "person.last_name"
EMAIL = "person.email"
PHONE_NUMBER = "person.phone_number"
STREET_ADDRESS = "person.street_address"
CITY = "person.city"
POSTAL_CODE = "person.postal_code"
COMMENT = "person.comment"
ACCOUNT_NUMBER = "person.account_number"
PGP_DATE = "pgp.pgp_date"
PGP_HANDLER = "pgp.pgp_handler"

PII = {
    "users_user": {
        "password": "person.password",
        "username": "person.username",
        "first_name": FIRST_NAME,
        "last_name": LAST_NAME,
        "email": EMAIL,
    },
    "users_profile": {
        "first_name": FIRST_NAME,
        "middle_name": FIRST_NAME,
        "last_name": LAST_NAME,
        "calling_name": FIRST_NAME,
        "email": EMAIL,
        "phone_number": PHONE_NUMBER,
        "phone_number_nightly": PHONE_NUMBER,
        "street_address": STREET_ADDRESS,
        "city": CITY,
        "postal_code": POSTAL_CODE,
        "date_of_birth": PGP_DATE,
        "national_identification_number": "pgp.pgp_hetu",
    },
    "users_userkeyvalue": {
        "value": "person.key_value",
    },
    "application_form_applicant": {
        "first_name": FIRST_NAME,
        "last_name": LAST_NAME,
        "email": EMAIL,
        "phone_number": PHONE_NUMBER,
        "street_address": STREET_ADDRESS,
        "city": CITY,
        "postal_code": POSTAL_CODE,
        "date_of_birth": PGP_DATE,
        "ssn_suffix": "pgp.pgp_ssn_suffix",
    },
    "application_form_application": {
        "sender_names": "person.sender_names",
        "handler_information": "person.handler_information",
    },
    "application_form_apartmentreservation": {
        "handler": PGP_HANDLER,
    },
    "application_form_offer": {
        "comment": COMMENT,
        "handler": PGP_HANDLER,
    },
    "application_form_lotteryevent": {
        "handler": PGP_HANDLER,
    },
    "application_form_apartmentreservationstatechangeevent": {
        "comment": COMMENT,
    },
    "application_form_apartmentqueuechangeevent": {
        "comment": COMMENT,
    },
    "customer_customer": {
        "additional_information": "person.additional_information",
    },
    "customer_customercomment": {
        "content": COMMENT,
    },
    "invoicing_apartmentinstallment": {
        "account_number": ACCOUNT_NUMBER,
        "reference_number": "person.reference_number",
        "handler": FIRST_NAME,
    },
    "invoicing_projectinstallmenttemplate": {
        "account_number": ACCOUNT_NUMBER,
    },
}

EXCLUDE_TABLES = [
    "public.django_session",
    "public.django_admin_log",
    "public.audit_log_auditlog",
    "public.resilient_logger_resilientlogentry",
    "public.asko_import_askoimportlogentry",
    "public.social_auth_usersocialauth",
    "public.social_auth_partial",
    "public.social_auth_code",
    "public.social_auth_nonce",
    "public.social_auth_association",
    "public.helusers_oidcbackchannellogoutevent",
    # Retry queue for Drupal payment sync: payload duplicates account and
    # reference numbers, and pending events must not be replayed elsewhere.
    "public.invoicing_drupalpaymentsyncoutboxevent",
]


# Field types that are structural (keys, relations, enums) and never sanitized.
STRUCTURAL_FIELD_TYPES = (
    models.AutoField,
    models.BigAutoField,
    models.ForeignKey,
    models.OneToOneField,
    EnumField,
)

# Type-based sanitizers, checked in order. DateTimeField must come before
# DateField, which it subclasses.
TYPE_SANITIZERS = (
    (models.TextField, "types.text"),
    (models.DateTimeField, "types.datetime"),
    (models.DateField, "types.date"),
    (models.DecimalField, "types.decimal"),
    (models.FloatField, "types.float"),
    (
        (
            models.IntegerField,
            models.SmallIntegerField,
            models.BigIntegerField,
            models.PositiveIntegerField,
            models.PositiveSmallIntegerField,
            models.PositiveBigIntegerField,
        ),
        "types.integer",
    ),
    (models.CharField, "types.char"),
)


def _is_structural_skip(field: models.Field) -> bool:
    """
    Return True when the field must stay unsanitized for dump integrity.

    Parameters:
        field (models.Field): Django model field.

    Returns:
        skip (bool): True when the field is structural (PK/FK/enum/auto time).
    """
    # DateTimeField subclasses DateField, so this covers both.
    is_auto_timestamp = isinstance(field, models.DateField) and (
        getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    )
    return bool(
        field.primary_key
        or isinstance(field, STRUCTURAL_FIELD_TYPES)
        or getattr(field, "choices", None)
        or is_auto_timestamp
    )


def _type_sanitizer_for_field(field: models.Field) -> str | None:
    """
    Return a type-based or PGP sanitizer id for a user-input field.

    Parameters:
        field (models.Field): Django model field.

    Returns:
        sanitizer_id (str | None): Strategy value, or None when not applicable.
    """
    if isinstance(field, PGPPublicKeyFieldMixin):
        return PGP_DATE if isinstance(field, DatePGPPublicKeyField) else "pgp.pgp_text"
    return next(
        (
            sanitizer
            for field_types, sanitizer in TYPE_SANITIZERS
            if isinstance(field, field_types)
        ),
        None,
    )


def _first_party_models() -> Iterator[type[models.Model]]:
    """Yield concrete (non-proxy) models of first-party apps."""
    return (
        model
        for model in apps.get_models()
        if model._meta.app_label in FIRST_PARTY_APPS and not model._meta.proxy
    )


def _heuristic_sanitizer(table: str, field: models.Field) -> str | None:
    """
    Return the type-based sanitizer for a column, or None to leave it as is.

    Parameters:
        table (str): Database table of the field's model.
        field (models.Field): Django model field.

    Returns:
        sanitizer_id (str | None): Strategy value, or None for named
        exclusions, structural fields and unsupported types.
    """
    if (table, field.column) in NAMED_EXCLUSIONS or _is_structural_skip(field):
        return None
    return _type_sanitizer_for_field(field)


def _apply_type_heuristics(strategy: dict[str, dict[str, Any]]) -> None:
    """
    Assign type-based sanitizers onto first-party model columns in place.

    Parameters:
        strategy (dict): Mutable table → column → sanitizer strategy map.
    """
    for model in _first_party_models():
        table = model._meta.db_table
        table_strategy = strategy.setdefault(table, {})
        for field in model._meta.local_fields:
            if field.column not in table_strategy:
                continue
            sanitizer = _heuristic_sanitizer(table, field)
            if sanitizer is not None:
                table_strategy[field.column] = sanitizer


def _apply_pii_overlay(strategy: dict[str, dict[str, Any]]) -> None:
    """
    Overlay explicit PII sanitizer mappings onto the strategy.

    Parameters:
        strategy (dict): Mutable table → column → sanitizer strategy map.

    Raises:
        SystemExit: When a PII column is missing from the strategy.
    """
    for table, fields in PII.items():
        table_strategy = strategy.setdefault(table, {})
        for column, sanitizer in fields.items():
            if column not in table_strategy:
                raise SystemExit(f"Missing column {table}.{column}")
            table_strategy[column] = sanitizer


def _ensure_users_user_strategy(strategy: dict[str, dict[str, Any]]) -> None:
    """
    Ensure ``users_user`` lists all concrete User columns.

    Proxy models can leave the table empty in ``from_models()``.
    """
    user = get_user_model()
    strategy["users_user"] = dict.fromkeys(
        [field.column for field in user._meta.local_fields]
    )


def build_sanitizer_strategy() -> dict[str, dict[str, Any]]:
    """
    Build the strategy section for `.sanitizerconfig`.

    Returns:
        strategy (dict): Table → column → sanitizer id or None.
    """
    conf = Configuration.from_models()
    strategy = conf.config["strategy"]
    _ensure_users_user_strategy(strategy)
    _apply_type_heuristics(strategy)
    _apply_pii_overlay(strategy)
    return strategy


def build_configuration() -> dict[str, Any]:
    """
    Build the full `.sanitizerconfig` document as a dict.

    Returns:
        config (dict): Root document with ``config`` and ``strategy`` keys.
    """
    conf = Configuration.from_models()
    _ensure_users_user_strategy(conf.config["strategy"])
    _apply_type_heuristics(conf.config["strategy"])
    _apply_pii_overlay(conf.config["strategy"])

    pg_dump_params = [
        "--format=plain",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
    ]
    pg_dump_params.extend(f"--exclude-table-data={t}" for t in EXCLUDE_TABLES)
    conf.config["config"]["extra_parameters"] = {"pg_dump": pg_dump_params}
    return conf.config
