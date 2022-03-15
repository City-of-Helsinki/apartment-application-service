from django.db import models
from django.db.models import JSONField


class AuditLog(models.Model):
    message = JSONField()

    def __str__(self):
        return " ".join(
            [
                _safe_get(self.message, "audit_event", "date_time"),
                _safe_get(self.message, "audit_event", "actor", "role"),
                _safe_get(self.message, "audit_event", "actor", "profile_id"),
                _safe_get(self.message, "audit_event", "operation"),
                _safe_get(self.message, "audit_event", "target", "type").upper(),
                _safe_get(self.message, "audit_event", "target", "id"),
            ]
        )


def _safe_get(value: dict, *keys: str) -> str:
    """Look up a nested key in the given dict, or return "UNKNOWN" on KeyError."""
    for key in keys:
        try:
            value = value[key]
        except KeyError:
            return "UNKNOWN"
    return str(value)
