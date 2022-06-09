from datetime import datetime, timezone
from pytest import fixture
from typing import Callable

from users.models import Profile, User
from users.tests.conftest import api_client, user_api_client  # noqa: F401
from users.tests.factories import ProfileFactory


@fixture
def profile() -> Profile:
    return ProfileFactory(id="73aa0891-32a3-42cb-a91f-284777bf1d7f")


@fixture
def other_profile() -> Profile:
    return ProfileFactory(id="f5cf186a-f9a8-4671-a7a5-1ecbe758071f")


@fixture
def fixed_datetime() -> Callable[[], datetime]:
    return lambda: datetime(2020, 6, 1, tzinfo=timezone.utc)


@fixture
def superuser() -> User:
    return User.objects.create_superuser("admin", "admin@example.com", "admin")
