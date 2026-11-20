"""
Test cases for the random password helper.
"""

import pytest

from users.masking import unmask_string
from users.passwords import generate_random_password
from users.services.drupal_credentials import build_masked_credentials

PASSWORD_ALLOWED_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def test_generate_random_password_default_length():
    """
    - A string of 32 characters is returned by default.
    """
    password = generate_random_password()

    assert isinstance(password, str)
    assert len(password) == 32


@pytest.mark.parametrize("length", [1, 12, 64])
def test_generate_random_password_custom_length(length):
    """
    - A string of the requested length is returned.
    """
    password = generate_random_password(length=length)

    assert isinstance(password, str)
    assert len(password) == length


def test_generate_random_password_uses_allowed_alphabet():
    """
    - Only characters from the unambiguous Django alphabet are used.
    """
    password = generate_random_password(length=1000)

    assert set(password) <= set(PASSWORD_ALLOWED_CHARS)


def test_generate_random_password_returns_different_values():
    """
    - Consecutive calls return different passwords.
    """
    assert generate_random_password() != generate_random_password()


@pytest.mark.parametrize("length", [0, -1, -32])
def test_generate_random_password_rejects_non_positive_length(length):
    """
    - ValueError is raised for a zero or negative length.
    """
    with pytest.raises(ValueError):
        generate_random_password(length=length)


@pytest.mark.django_db
def test_build_masked_credentials_generates_helper_compatible_password(profile):
    """
    - build_masked_credentials returns a 32 character password.
    - The password only uses the generate_random_password alphabet.
    - The password is stored on the profile user.
    - Asserted by behaviour, so the call site import style is not relevant.
    """
    credentials = build_masked_credentials(profile)
    password = unmask_string(credentials["password"])

    profile.user.refresh_from_db()
    assert len(password) == 32
    assert set(password) <= set(PASSWORD_ALLOWED_CHARS)
    assert profile.user.check_password(password)
