from django.conf import settings
from hashids import Hashids
from uuid import UUID

_hashids = Hashids(salt=settings.HASHIDS_SALT)


def mask_uuid(value: UUID) -> str:
    """Mask the given UUID using its 128-bit integer representation."""
    return _hashids.encode(value.int)


def unmask_uuid(masked_uuid: str) -> UUID:
    """
    Unmask the given masked value. If the the masked value cannot be decoded
    or the integer value is outside the UUID 128-bit range, a nil UUID will
    be returned.
    """
    try:
        integer_value = _hashids.decode(masked_uuid)[0]
        return UUID(int=integer_value)
    except (IndexError, ValueError):
        return UUID(int=0)


def mask_string(value: str) -> str:
    """
    Mask the given string. First, the bytes of the string will be
    interpreted as an integer, then that integer is masked using Hashids.
    """
    string_bytes = value.encode()
    integer_value = int.from_bytes(string_bytes, "little")
    assert integer_value >= 0
    return _hashids.encode(integer_value)


def unmask_string(masked_string: str) -> str:
    """
    Unmask the given masked value. First, the value will be decoded using
    Hashids, then the decoded integer will be interpreted as bytes forming
    the unmasked string.
    """
    try:
        integer_value = _hashids.decode(masked_string)[0]
        string_length = (integer_value.bit_length() + 7) // 8
        string_bytes = integer_value.to_bytes(string_length, "little")
        return string_bytes.decode()
    except IndexError:
        return ""
