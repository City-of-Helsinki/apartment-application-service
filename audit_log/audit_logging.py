import json
import logging
from datetime import datetime, timezone
from django.db.models import Model
from typing import Callable, Optional

from audit_log.enums import Operation, Role, Status
from users.models import Profile

ORIGIN = "APARTMENT_APPLICATION_SERVICE"


def _now() -> datetime:
    """Returns the current time in UTC timezone."""
    return datetime.now(tz=timezone.utc)


def _iso8601_date(time: datetime) -> str:
    """Formats the timestamp in ISO-8601 format, e.g. '2020-06-01T00:00:00.000Z'."""
    return f"{time.replace(tzinfo=None).isoformat(sep='T', timespec='milliseconds')}Z"


def log(
    actor: Optional[Profile],
    operation: Operation,
    target: Model,
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
    role = Role.OWNER if actor is not None else Role.SYSTEM
    message = {
        "audit_event": {
            "origin": ORIGIN,
            "status": str(status.value),
            "date_time_epoch": int(current_time.timestamp() * 1000),
            "date_time": _iso8601_date(current_time),
            "actor": {
                "role": str(role.value),
                "profile_id": str(actor.pk) if actor else None,
            },
            "operation": str(operation.value),
            "target": {
                "id": str(target.pk),
                "type": str(target.__class__.__name__),
            },
        },
    }
    logger = logging.getLogger("audit")
    logger.info(json.dumps(message))
