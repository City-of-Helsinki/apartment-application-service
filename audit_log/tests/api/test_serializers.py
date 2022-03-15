from pytest import mark

from audit_log.api.serializers import AuditLogSerializer

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


@mark.django_db
def test_audit_log_serializer_create():
    serializer = AuditLogSerializer(data=_common_fields)
    assert serializer.is_valid()
    audit_log = serializer.save()
    assert audit_log
    assert audit_log.id
