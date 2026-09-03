"""
Build `.sanitizerconfig` strategy from Django models.

Applies type-based sanitizers for user-input fields on first-party apps,
skips structural fields, applies named exclusions, then overlays explicit
PII mappings.
"""

from __future__ import annotations

from typing import Any

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
    }
)

PII = {
    "users_user": {
        "password": "person.password",
        "username": "person.username",
        "first_name": "person.first_name",
        "last_name": "person.last_name",
        "email": "person.email",
    },
    "users_profile": {
        "first_name": "person.first_name",
        "middle_name": "person.first_name",
        "last_name": "person.last_name",
        "calling_name": "person.first_name",
        "email": "person.email",
        "phone_number": "person.phone_number",
        "phone_number_nightly": "person.phone_number",
        "street_address": "person.street_address",
        "city": "person.city",
        "postal_code": "person.postal_code",
        "date_of_birth": "pgp.pgp_date",
        "national_identification_number": "pgp.pgp_hetu",
    },
    "users_userkeyvalue": {
        "value": "person.key_value",
    },
    "application_form_applicant": {
        "first_name": "person.first_name",
        "last_name": "person.last_name",
        "email": "person.email",
        "phone_number": "person.phone_number",
        "street_address": "person.street_address",
        "city": "person.city",
        "postal_code": "person.postal_code",
        "date_of_birth": "pgp.pgp_date",
        "ssn_suffix": "pgp.pgp_ssn_suffix",
    },
    "application_form_application": {
        "sender_names": "person.sender_names",
        "handler_information": "person.handler_information",
    },
    "application_form_apartmentreservation": {
        "handler": "pgp.pgp_handler",
    },
    "application_form_offer": {
        "comment": "person.comment",
        "handler": "pgp.pgp_handler",
    },
    "application_form_lotteryevent": {
        "handler": "pgp.pgp_handler",
    },
    "application_form_apartmentreservationstatechangeevent": {
        "comment": "person.comment",
    },
    "application_form_apartmentqueuechangeevent": {
        "comment": "person.comment",
    },
    "customer_customer": {
        "additional_information": "person.additional_information",
    },
    "customer_customercomment": {
        "content": "person.comment",
    },
    "invoicing_apartmentinstallment": {
        "account_number": "person.account_number",
        "reference_number": "person.reference_number",
        "handler": "person.first_name",
    },
    "invoicing_projectinstallmenttemplate": {
        "account_number": "person.account_number",
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
]


def _is_structural_skip(field: models.Field) -> bool:
    """
    Return True when the field must stay unsanitized for dump integrity.

    Parameters:
        field (models.Field): Django model field.

    Returns:
        skip (bool): True when the field is structural (PK/FK/enum/auto time).
    """
    if field.primary_key:
        return True
    if isinstance(field, (models.AutoField, models.BigAutoField)):
        return True
    if isinstance(field, (models.ForeignKey, models.OneToOneField)):
        return True
    if isinstance(field, EnumField):
        return True
    if getattr(field, "choices", None):
        return True
    if isinstance(field, models.DateTimeField) and (
        getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    ):
        return True
    if isinstance(field, models.DateField) and (
        getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False)
    ):
        return True
    return False


def _type_sanitizer_for_field(field: models.Field) -> str | None:
    """
    Return a type-based or PGP sanitizer id for a user-input field.

    Parameters:
        field (models.Field): Django model field.

    Returns:
        sanitizer_id (str | None): Strategy value, or None when not applicable.
    """
    if isinstance(field, PGPPublicKeyFieldMixin):
        if isinstance(field, DatePGPPublicKeyField):
            return "pgp.pgp_date"
        return "pgp.pgp_text"

    if isinstance(field, models.TextField):
        return "types.text"
    if isinstance(field, models.DateTimeField):
        return "types.datetime"
    if isinstance(field, models.DateField):
        return "types.date"
    if isinstance(field, models.DecimalField):
        return "types.decimal"
    if isinstance(field, models.FloatField):
        return "types.float"
    if isinstance(
        field,
        (
            models.IntegerField,
            models.SmallIntegerField,
            models.BigIntegerField,
            models.PositiveIntegerField,
            models.PositiveSmallIntegerField,
            models.PositiveBigIntegerField,
        ),
    ):
        return "types.integer"
    if isinstance(field, models.CharField):
        return "types.char"
    return None


def _apply_type_heuristics(strategy: dict[str, dict[str, Any]]) -> None:
    """
    Assign type-based sanitizers onto first-party model columns in place.

    Parameters:
        strategy (dict): Mutable table → column → sanitizer strategy map.
    """
    for model in apps.get_models():
        if model._meta.app_label not in FIRST_PARTY_APPS:
            continue
        if model._meta.proxy:
            continue
        table = model._meta.db_table
        table_strategy = strategy.setdefault(table, {})
        for field in model._meta.local_fields:
            column = field.column
            if column not in table_strategy:
                continue
            if (table, column) in NAMED_EXCLUSIONS:
                continue
            if _is_structural_skip(field):
                continue
            sanitizer = _type_sanitizer_for_field(field)
            if sanitizer is not None:
                table_strategy[column] = sanitizer


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
