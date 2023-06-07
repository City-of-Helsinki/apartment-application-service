import pytest
from datetime import datetime, timedelta
from django.contrib.auth.models import AnonymousUser
from django.test import override_settings
from django.utils import timezone
from unittest import mock

from audit_log import audit_logging
from audit_log.enums import Operation, Status
from audit_log.models import AuditLog
from audit_log.tasks import clear_audit_log_entries, send_audit_log_to_elastic_search

_common_fields = {
    "audit_event": {
        "origin": "APARTMENT_APPLICATION_SERVICE",
        "status": "SUCCESS",
        "date_time_epoch": 1590969600000,
        "date_time": "2020-06-01T00:00:00.000Z",
        "actor": {
            "role": "OWNER",
            "profile_id": "73aa0891-32a3-42cb-a91f-284777bf1d7f",
        },
        "operation": "READ",
        "target": {
            "id": "73aa0891-32a3-42cb-a91f-284777bf1d7f",
            "type": "Profile",
        },
    }
}


@pytest.mark.django_db
def test_log_logs_at_info_level(caplog, profile):
    audit_logging.log(profile, Operation.READ, profile)
    for record in caplog.records:
        assert record.levelname == "INFO"


@pytest.mark.django_db
@pytest.mark.parametrize("operation", list(Operation))
def test_log_owner_operation(fixed_datetime, profile, operation):
    audit_logging.log(profile, operation, profile, get_time=fixed_datetime)
    message = AuditLog.objects.get().message
    assert message == {
        **_common_fields,
        "audit_event": {**_common_fields["audit_event"], "operation": operation.value},
    }


@pytest.mark.django_db
def test_log_anonymous_role(fixed_datetime, profile):
    audit_logging.log(AnonymousUser(), Operation.READ, profile, get_time=fixed_datetime)
    message = AuditLog.objects.get().message
    assert message == {
        **_common_fields,
        "audit_event": {
            **_common_fields["audit_event"],
            "actor": {"role": "ANONYMOUS", "profile_id": None},
        },
    }


@pytest.mark.django_db
def test_log_user_role(fixed_datetime, profile, other_profile):
    audit_logging.log(profile, Operation.READ, other_profile, get_time=fixed_datetime)
    message = AuditLog.objects.get().message
    assert message == {
        **_common_fields,
        "audit_event": {
            **_common_fields["audit_event"],
            "actor": {"role": "USER", "profile_id": str(profile.pk)},
            "target": {"id": str(other_profile.pk), "type": "Profile"},
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize("operation", list(Operation))
def test_log_system_operation(fixed_datetime, profile, operation):
    audit_logging.log(None, operation, profile, get_time=fixed_datetime)
    message = AuditLog.objects.get().message
    assert message == {
        **_common_fields,
        "audit_event": {
            **_common_fields["audit_event"],
            "operation": operation.value,
            "actor": {"role": "SYSTEM", "profile_id": None},
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize("status", list(Status))
def test_log_status(fixed_datetime, profile, status):
    audit_logging.log(profile, Operation.READ, profile, status, get_time=fixed_datetime)
    message = AuditLog.objects.get().message
    assert message == {
        **_common_fields,
        "audit_event": {**_common_fields["audit_event"], "status": status.value},
    }


@pytest.mark.django_db
def test_log_origin(fixed_datetime, profile):
    audit_logging.log(profile, Operation.READ, profile, get_time=fixed_datetime)
    message = AuditLog.objects.get().message
    assert message["audit_event"]["origin"] == "APARTMENT_APPLICATION_SERVICE"


@pytest.mark.django_db
def test_log_current_timestamp(profile):
    tolerance = timedelta(seconds=1)
    date_before_logging = datetime.now(tz=timezone.utc) - tolerance
    audit_logging.log(profile, Operation.READ, profile)
    date_after_logging = datetime.now(tz=timezone.utc) + tolerance
    message = AuditLog.objects.get().message
    logged_date_from_date_time_epoch = datetime.fromtimestamp(
        int(message["audit_event"]["date_time_epoch"]) / 1000, tz=timezone.utc
    )
    assert date_before_logging <= logged_date_from_date_time_epoch <= date_after_logging
    logged_date_from_date_time = datetime.strptime(
        message["audit_event"]["date_time"], "%Y-%m-%dT%H:%M:%S.%f%z"
    )
    assert date_before_logging <= logged_date_from_date_time <= date_after_logging


@pytest.mark.django_db
@override_settings(
    ENABLE_SEND_AUDIT_LOG=True,
)
def test_send_audit_log_missing_configuration(profile, fixed_datetime):
    audit_logging.log(
        profile,
        Operation.READ,
        profile,
        get_time=fixed_datetime,
    )
    assert AuditLog.objects.count() == 1
    entry = AuditLog.objects.first()
    assert entry.sent_at is None
    send_audit_log_to_elastic_search()
    assert entry.sent_at is None


@pytest.mark.parametrize(
    "result_value, expected_status",
    [("created", True), ("failed", False)],  # Log sent successfully
)
@pytest.mark.django_db
@override_settings(
    AUDIT_LOG_ELASTICSEARCH_HOST="example.com",
    AUDIT_LOG_ELASTICSEARCH_PORT="1234",
    AUDIT_LOG_ELASTICSEARCH_USERNAME="e_user",
    AUDIT_LOG_ELASTICSEARCH_PASSWORD="e_password",
    ENABLE_SEND_AUDIT_LOG=True,
)
def test_send_audit_log_success(profile, fixed_datetime, result_value, expected_status):
    audit_logging.log(
        profile,
        Operation.READ,
        profile,
        get_time=fixed_datetime,
    )
    assert AuditLog.objects.count() == 1
    assert AuditLog.objects.first().sent_at is None

    with mock.patch("elasticsearch.Elasticsearch.index") as elasticsearch_index_mock:
        elasticsearch_index_mock.return_value = {"result": result_value}
        send_audit_log_to_elastic_search()
        assert (AuditLog.objects.first().sent_at is not None) == expected_status


@pytest.mark.django_db
@override_settings(CLEAR_AUDIT_LOG_ENTRIES=True)
def test_clear_audit_log(profile, fixed_datetime):
    audit_logging.log(
        profile,
        Operation.READ,
        profile,
        get_time=fixed_datetime,
    )
    audit_logging.log(
        profile,
        Operation.READ,
        profile,
        get_time=fixed_datetime,
    )
    audit_logging.log(
        profile,
        Operation.READ,
        profile,
        get_time=fixed_datetime,
    )
    assert AuditLog.objects.count() == 3

    new_sent_log = AuditLog.objects.all()[0]
    expired_unsent_log = AuditLog.objects.all()[1]
    expired_sent_log = AuditLog.objects.all()[2]

    new_sent_log.sent_at = timezone.now()
    new_sent_log.save()

    expired_unsent_log.created_at = timezone.now() - timedelta(days=35)
    expired_unsent_log.save()

    expired_sent_log.sent_at = timezone.now()
    expired_sent_log.created_at = timezone.now() - timedelta(days=35)
    expired_sent_log.save()

    clear_audit_log_entries()
    assert AuditLog.objects.count() == 2
    assert AuditLog.objects.filter(id=new_sent_log.id).exists()
    assert AuditLog.objects.filter(id=expired_unsent_log.id).exists()
