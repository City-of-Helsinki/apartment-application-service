from datetime import datetime, timezone
from typing import Callable, Optional, Union

from django.contrib.auth.models import AnonymousUser
from django.db.models import Model

from audit_log.enums import Operation, Role, Status
from audit_log.models import AuditLog
from users.models import Profile

ORIGIN = "APARTMENT_APPLICATION_SERVICE"


def _now() -> datetime:
    """Returns the current time in UTC timezone."""
    return datetime.now(tz=timezone.utc)


def _iso8601_date(time: datetime) -> str:
    """Formats the timestamp in ISO-8601 format, e.g. '2020-06-01T00:00:00.000Z'."""
    return f"{time.replace(tzinfo=None).isoformat(sep='T', timespec='milliseconds')}Z"


def log(
    actor: Optional[Union[Profile, AnonymousUser]],
    operation: Operation,
    target: Optional[Model],
    status: Status = Status.SUCCESS,
    get_time: Callable[[], datetime] = _now,
):
    """
    Write an event to the audit log.

    Each audit log event has an actor (or None for system events),
    an operation(e.g. READ or UPDATE), the target of the operation
    (a Django model instance), status (e.g. SUCCESS), and a timestamp.

    Audit log events are written to the "audit" logger at "INFO" level.
    """
    current_time = get_time()
    profile_id = None
    if actor is None:
        role = Role.SYSTEM
    elif isinstance(actor, AnonymousUser):
        role = Role.ANONYMOUS
    elif actor.id == target.pk:
        role = Role.OWNER
        profile_id = str(actor.pk)
    else:
        role = Role.USER
        profile_id = str(actor.pk)
    message = {
        "audit_event": {
            "origin": ORIGIN,
            "status": str(status.value),
            "date_time_epoch": int(current_time.timestamp() * 1000),
            "date_time": _iso8601_date(current_time),
            "actor": {
                "role": str(role.value),
                "profile_id": profile_id,
            },
            "operation": str(operation.value),
            "target": {
                "id": _get_target_id(target),
                "type": target and str(target.__class__.__name__) or None,
            },
        },
    }
    AuditLog.objects.create(message=message)


def _get_target_id(instance: Optional[Model]) -> Optional[str]:
    if instance is None or instance.pk is None:
        return None
    field_name = getattr(instance, "audit_log_id_field", "pk")
    audit_log_id = getattr(instance, field_name, None)
    return str(audit_log_id)
