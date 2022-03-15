from audit_log.models import AuditLog


def test_audit_log_string_representation_with_all_fields_present():
    time = "2020-06-01T00:00:00.000Z"
    uuid = "f1e33c3b-2137-4bf1-926f-0a2ca013f0b5"
    log = AuditLog(
        message={
            "audit_event": {
                "origin": "APARTMENT_APPLICATION_SERVICE",
                "status": "SUCCESS",
                "date_time_epoch": 1590969600000,
                "date_time": time,
                "actor": {"role": "OWNER", "profile_id": uuid},
                "operation": "READ",
                "target": {"id": uuid, "type": "Profile"},
            }
        }
    )
    assert str(log) == f"{time} OWNER {uuid} READ PROFILE {uuid}"


def test_audit_log_string_representation_missing_field_is_replaced_with_unknown():
    time = "2020-06-01T00:00:00.000Z"
    uuid = "e69600ec-1a2d-4839-b4b8-8c807dd7e5d4"
    log = AuditLog(
        message={
            "audit_event": {
                "origin": "APARTMENT_APPLICATION_SERVICE",
                "status": "SUCCESS",
                "date_time_epoch": 1590969600000,
                "date_time": time,
                "actor": {"role": "USER", "profile_id": uuid},
                "operation": "WRITE",
                "target": {"id": uuid},
            }
        }
    )
    assert str(log) == f"{time} USER {uuid} WRITE UNKNOWN {uuid}"
