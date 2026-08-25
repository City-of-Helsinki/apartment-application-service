"""Generate .sanitizerconfig from Django models with PII strategies applied."""

import yaml
from django.contrib.auth import get_user_model
from sanitized_dump.config import Configuration

conf = Configuration.from_models()
User = get_user_model()
conf.config["strategy"]["users_user"] = dict.fromkeys(
    [f.column for f in User._meta.local_fields]
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

for table, fields in PII.items():
    strategy = conf.config["strategy"].setdefault(table, {})
    for column, sanitizer in fields.items():
        if column not in strategy:
            raise SystemExit(f"Missing column {table}.{column}")
        strategy[column] = sanitizer

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

pg_dump_params = [
    "--format=plain",
    "--clean",
    "--if-exists",
    "--no-owner",
    "--no-acl",
]
pg_dump_params.extend(f"--exclude-table-data={t}" for t in EXCLUDE_TABLES)

conf.config["config"]["extra_parameters"] = {"pg_dump": pg_dump_params}

out = yaml.dump(
    conf.config, default_flow_style=False, allow_unicode=True, sort_keys=True
)
with open("/app/.sanitizerconfig", "w") as handle:
    handle.write(out)
print("Wrote .sanitizerconfig")
print("PII mappings:", sum(len(v) for v in PII.values()))
