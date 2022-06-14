import pytest
from dateutil import parser
from django.urls import reverse
from rest_framework import status

from audit_log.models import AuditLog

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
def test_audit_log_post_writes_audit_log_without_authorized_user(api_client):
    data = _common_fields
    response = api_client.post(reverse("audit_log:auditlog-list"), data, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_audit_log_post_writes_audit_log_with_authorized_user(salesperson_api_client):
    data = _common_fields
    salesperson_api_client.post(reverse("audit_log:auditlog-list"), data, format="json")
    audit_event = AuditLog.objects.get().message["audit_event"]

    assert audit_event["origin"] == data["audit_event"]["origin"]
    assert audit_event["status"] == data["audit_event"]["status"]
    assert audit_event["date_time_epoch"] == data["audit_event"]["date_time_epoch"]
    assert parser.isoparse(audit_event["date_time"]) == parser.isoparse(
        data["audit_event"]["date_time"]
    )
    assert audit_event["actor"] == {
        "role": data["audit_event"]["actor"]["role"],
        "profile_id": data["audit_event"]["actor"]["profile_id"],
    }
    assert audit_event["operation"] == data["audit_event"]["operation"]
    assert audit_event["target"] == {
        "id": data["audit_event"]["target"]["id"],
        "type": data["audit_event"]["target"]["type"],
    }


@pytest.mark.django_db
def test_audit_log_get_not_allowed(salesperson_api_client):
    response = salesperson_api_client.get(reverse("audit_log:auditlog-list"))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_audit_log_put_not_allowed(salesperson_api_client):
    response = salesperson_api_client.put(reverse("audit_log:auditlog-list"))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_audit_log_patch_not_allowed(salesperson_api_client):
    response = salesperson_api_client.patch(reverse("audit_log:auditlog-list"))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


@pytest.mark.django_db
def test_audit_log_delete_not_allowed(salesperson_api_client):
    response = salesperson_api_client.delete(reverse("audit_log:auditlog-list"))
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
