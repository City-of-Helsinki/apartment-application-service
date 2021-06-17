from json import JSONDecodeError, loads
from typing import Optional


def get_audit_log_event(caplog) -> Optional[dict]:
    for record in caplog.records:
        try:
            message = loads(record.message)
            if "audit_event" in message:
                return message["audit_event"]
        except JSONDecodeError:
            pass
    return None
