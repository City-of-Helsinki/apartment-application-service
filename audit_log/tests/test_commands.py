import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from resilient_logger.models import ResilientLogEntry


@pytest.mark.django_db
def test_generate_audit_log_test_entries_creates_expected_amount():
    call_command("generate_audit_log_test_entries", count=3)

    entries = ResilientLogEntry.objects.order_by("created_at")
    assert entries.count() == 3
    for entry in entries:
        assert entry.context["actor"] == {"role": "SYSTEM", "profile_id": None}
        assert entry.context["operation"] == "READ"
        assert entry.context["target"] == {"id": None, "type": None}


@pytest.mark.django_db
def test_generate_audit_log_test_entries_rejects_non_positive_count():
    with pytest.raises(CommandError, match="Count must be a positive integer."):
        call_command("generate_audit_log_test_entries", count=0)
