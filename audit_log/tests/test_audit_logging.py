import logging
from datetime import datetime, timedelta

import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from resilient_logger.models import ResilientLogEntry
from resilient_logger.sources import ResilientLogSource

from audit_log import audit_logging
from audit_log.enums import Operation, Status

_common_context = {
    "date_time_epoch": 1590969600000,
    "date_time": "2020-06-01T00:00:00.000Z",
}


@pytest.mark.django_db
def test_log_logs_at_info_level(profile):
    audit_logging.log(profile, Operation.READ, profile)
    entry = ResilientLogEntry.objects.get()
    assert entry.level == logging.INFO
    assert entry.message == Status.SUCCESS.value


@pytest.mark.django_db
@pytest.mark.parametrize("operation", list(Operation))
def test_log_owner_operation(fixed_datetime, profile, operation):
    audit_logging.log(profile, operation, profile, get_time=fixed_datetime)
    entry = ResilientLogEntry.objects.get()
    assert entry.message == Status.SUCCESS.value
    assert entry.context["actor"] == {
        "role": "OWNER",
        "profile_id": str(profile.pk),
    }
    assert entry.context["operation"] == operation.value
    assert entry.context["target"] == {
        "id": str(profile.pk),
        "type": "Profile",
    }
    assert entry.context["status"] == Status.SUCCESS.value
    assert entry.context["date_time_epoch"] == _common_context["date_time_epoch"]
    assert entry.context["date_time"] == _common_context["date_time"]


@pytest.mark.django_db
def test_log_anonymous_role(fixed_datetime, profile):
    audit_logging.log(AnonymousUser(), Operation.READ, profile, get_time=fixed_datetime)
    entry = ResilientLogEntry.objects.get()
    assert entry.message == Status.SUCCESS.value
    assert entry.context["actor"] == {"role": "ANONYMOUS", "profile_id": None}
    assert entry.context["operation"] == Operation.READ.value
    assert entry.context["target"] == {
        "id": str(profile.pk),
        "type": "Profile",
    }
    assert entry.context["status"] == Status.SUCCESS.value
    assert entry.context["date_time_epoch"] == _common_context["date_time_epoch"]
    assert entry.context["date_time"] == _common_context["date_time"]


@pytest.mark.django_db
def test_log_user_role(fixed_datetime, profile, other_profile):
    audit_logging.log(profile, Operation.READ, other_profile, get_time=fixed_datetime)
    entry = ResilientLogEntry.objects.get()
    assert entry.message == Status.SUCCESS.value
    assert entry.context["actor"] == {"role": "USER", "profile_id": str(profile.pk)}
    assert entry.context["operation"] == Operation.READ.value
    assert entry.context["target"] == {
        "id": str(other_profile.pk),
        "type": "Profile",
    }
    assert entry.context["status"] == Status.SUCCESS.value
    assert entry.context["date_time_epoch"] == _common_context["date_time_epoch"]
    assert entry.context["date_time"] == _common_context["date_time"]


@pytest.mark.django_db
@pytest.mark.parametrize("operation", list(Operation))
def test_log_system_operation(fixed_datetime, profile, operation):
    audit_logging.log(None, operation, profile, get_time=fixed_datetime)
    entry = ResilientLogEntry.objects.get()
    assert entry.message == Status.SUCCESS.value
    assert entry.context["actor"] == {"role": "SYSTEM", "profile_id": None}
    assert entry.context["operation"] == operation.value
    assert entry.context["target"] == {
        "id": str(profile.pk),
        "type": "Profile",
    }
    assert entry.context["status"] == Status.SUCCESS.value
    assert entry.context["date_time_epoch"] == _common_context["date_time_epoch"]
    assert entry.context["date_time"] == _common_context["date_time"]


@pytest.mark.django_db
@pytest.mark.parametrize("status", list(Status))
def test_log_status(fixed_datetime, profile, status):
    audit_logging.log(profile, Operation.READ, profile, status, get_time=fixed_datetime)
    entry = ResilientLogEntry.objects.get()
    assert entry.message == status.value
    assert entry.context["status"] == status.value
    assert entry.context["operation"] == Operation.READ.value
    assert entry.context["actor"] == {"role": "OWNER", "profile_id": str(profile.pk)}


@pytest.mark.django_db
def test_log_origin(fixed_datetime, profile):
    audit_logging.log(profile, Operation.READ, profile, get_time=fixed_datetime)
    entry = ResilientLogEntry.objects.get()
    document = ResilientLogSource(entry).get_document()
    assert document["audit_event"]["origin"] == settings.RESILIENT_LOGGER["origin"]


@pytest.mark.django_db
def test_log_current_timestamp(profile):
    tolerance = timedelta(seconds=1)
    date_before_logging = datetime.now(tz=timezone.utc) - tolerance
    audit_logging.log(profile, Operation.READ, profile)
    date_after_logging = datetime.now(tz=timezone.utc) + tolerance
    entry = ResilientLogEntry.objects.get()
    logged_date_from_date_time_epoch = datetime.fromtimestamp(
        int(entry.context["date_time_epoch"]) / 1000, tz=timezone.utc
    )
    assert date_before_logging <= logged_date_from_date_time_epoch <= date_after_logging
    logged_date_from_date_time = datetime.strptime(
        entry.context["date_time"], "%Y-%m-%dT%H:%M:%S.%f%z"
    )
    assert date_before_logging <= logged_date_from_date_time <= date_after_logging
