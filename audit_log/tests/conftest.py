from datetime import datetime, timezone
from pytest import fixture
from typing import Callable

from users.models import Profile
from users.tests.factories import ProfileFactory


@fixture
def profile() -> Profile:
    return ProfileFactory(id="73aa0891-32a3-42cb-a91f-284777bf1d7f")


@fixture
def fixed_datetime() -> Callable[[], datetime]:
    return lambda: datetime(2020, 6, 1, tzinfo=timezone.utc)
