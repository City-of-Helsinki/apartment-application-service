from uuid import UUID

from django.test import override_settings

from users.masking import mask_string, mask_uuid, unmask_string, unmask_uuid

TEST_SALT = "test salt"


@override_settings(HASHIDS_SALT=TEST_SALT)
def test_mask_uuid():
    uuid = UUID("32874441-ff6b-4e86-8953-822ce3f34e80")
    assert mask_uuid(uuid) == "mZwKmwvykkAjlnJyPDoG6MA7E"


@override_settings(HASHIDS_SALT=TEST_SALT)
def test_unmask_uuid():
    uuid = UUID("32874441-ff6b-4e86-8953-822ce3f34e80")
    assert unmask_uuid("mZwKmwvykkAjlnJyPDoG6MA7E") == uuid


@override_settings(HASHIDS_SALT=TEST_SALT)
def test_unmask_uuid_returns_nil_uuid_on_error():
    assert unmask_uuid("INVALID") == UUID("00000000-0000-0000-0000-000000000000")


@override_settings(HASHIDS_SALT=TEST_SALT)
def test_mask_string():
    assert mask_string("test") == "N5M5pJv"


@override_settings(HASHIDS_SALT=TEST_SALT)
def test_unmask_string():
    assert unmask_string("N5M5pJv") == "test"


@override_settings(HASHIDS_SALT=TEST_SALT)
def test_unmask_string_returns_empty_string_on_error():
    assert unmask_string("INVALID") == ""
