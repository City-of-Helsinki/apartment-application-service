from unittest.mock import Mock

from django.contrib.admin import AdminSite
from pytest import mark

from audit_log.admin import AuditLogAdmin
from audit_log.models import AuditLog


@mark.django_db
def test_audit_log_admin_message_prettified(superuser):
    request = Mock(user=superuser)
    model_admin = AuditLogAdmin(AuditLog, AdminSite())
    assert list(model_admin.get_fields(request)) == [
        "message_prettified",
        "sent_at",
        "created_at",
    ]


@mark.django_db
def test_audit_log_admin_permissions(superuser):
    request = Mock(user=superuser)
    audit_log = AuditLog.objects.create(message={})
    model_admin = AuditLogAdmin(AuditLog, AdminSite())
    # The user should have permission to view but not modify or delete audit logs
    assert model_admin.has_view_permission(request, audit_log)
    assert not model_admin.has_add_permission(request)
    assert not model_admin.has_change_permission(request, audit_log)
    assert not model_admin.has_delete_permission(request, audit_log)
