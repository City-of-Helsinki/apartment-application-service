import factory
import random
from datetime import datetime
from django.contrib.auth.models import Group
from factory import Faker, fuzzy, LazyAttribute, post_generation

from users.enums import Roles
from users.models import Profile, User

CONTACT_LANGUAGE_CHOICES = ["fi", "sv", "en"]


def fake_national_identification_number(birthday: datetime.date) -> str:
    """
    Create a fake person identity code.
    """
    birth_string = birthday.strftime("%d%m%y")
    century_sign = "+-A"[birthday.year // 100 - 18]
    individual_number = f"{random.randint(3, 899):03d}"
    index = int(birth_string + individual_number) % 31
    control_character = "0123456789ABCDEFHJKLMNPRSTUVWXY"[index]
    ssn = birth_string + century_sign + individual_number + control_character
    return ssn


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    first_name = Faker("first_name")
    last_name = Faker("last_name")
    email = Faker("email")


class ProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Profile

    id = factory.Faker("uuid4")
    first_name = Faker("first_name")
    middle_name = Faker("first_name")
    last_name = Faker("last_name")
    calling_name = LazyAttribute(lambda x: x.first_name)
    email = Faker("email")
    phone_number = Faker("phone_number")
    phone_number_nightly = Faker("phone_number")
    street_address = Faker("street_address")
    city = Faker("city")
    postal_code = Faker("postcode")
    date_of_birth = Faker("date_of_birth", minimum_age=17, maximum_age=99)
    national_identification_number = LazyAttribute(
        lambda x: fake_national_identification_number(x.date_of_birth)
    )
    contact_language = fuzzy.FuzzyChoice(list(CONTACT_LANGUAGE_CHOICES))
    user = factory.SubFactory(UserFactory)


class SalespersonProfileFactory(ProfileFactory):
    @post_generation
    def post(obj, create, extracted, **kwargs):
        if not create:
            return

        group = Group.objects.get(name__iexact=Roles.SALESPERSON.name)
        group.user_set.add(obj.user)
