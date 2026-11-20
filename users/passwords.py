"""Random password generation for API credentials."""

import secrets

# Django's former make_random_password() default; ambiguous characters
# (i, l, o, I, O, 0, 1) are excluded.
PASSWORD_ALLOWED_CHARS = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_random_password(length: int = 32) -> str:
    """
    Return a cryptographically secure random password.

            Parameters:
                    length (int): Number of characters, must be at least 1

            Returns:
                    password (str): Random string from PASSWORD_ALLOWED_CHARS

            Raises:
                    ValueError: If length is less than 1
    """
    if length < 1:
        raise ValueError("Password length must be at least 1.")
    return "".join(secrets.choice(PASSWORD_ALLOWED_CHARS) for _ in range(length))
