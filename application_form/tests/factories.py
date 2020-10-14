import factory
import uuid
from django.contrib.auth import get_user_model
from factory import fuzzy

from application_form.models import (
    CURRENT_HOUSING_CHOICES,
    HasoApplication,
    HitasApplication,
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: "user_%d" % (n + 1))


class HasoApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HasoApplication

    running_number = fuzzy.FuzzyText()
    current_housing = fuzzy.FuzzyChoice([c[0] for c in CURRENT_HOUSING_CHOICES])
    housing_description = fuzzy.FuzzyText()
    housing_type = fuzzy.FuzzyText()
    housing_area = fuzzy.FuzzyFloat(0, 1000)
    is_changing_occupancy_apartment = True
    is_over_55 = True
    project_uuid = uuid.uuid4()
    apartment_uuids = factory.List([uuid.uuid4() for _ in range(2)])


class HitasApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HitasApplication

    has_previous_hitas_apartment = True
    previous_hitas_description = fuzzy.FuzzyText()
    has_children = True
    project_uuid = uuid.uuid4()
    apartment_uuid = uuid.uuid4()
