import factory
import random
from factory import Faker, fuzzy, LazyAttribute
from typing import List

from apartment.tests.factories import ApartmentFactory
from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models import (
    ApartmentReservation,
    Applicant,
    Application,
    ApplicationApartment,
    LotteryEvent,
    LotteryEventResult,
)
from application_form.services.application import _calculate_age
from users.tests.factories import ProfileFactory


def calculate_ssn_suffix(obj) -> str:
    date_string = obj.date_of_birth.strftime("%d%m%y")
    century_sign = "+-A"[obj.date_of_birth.year // 100 - 18]
    individual_number = f"{random.randint(3, 899):03d}"
    index = int(date_string + individual_number) % 31
    control_character = "0123456789ABCDEFHJKLMNPRSTUVWXY"[index]
    ssn_suffix = century_sign + individual_number + control_character
    return ssn_suffix


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application

    external_uuid = factory.Faker("uuid4")
    applicants_count = fuzzy.FuzzyInteger(1, 2)
    type = fuzzy.FuzzyChoice(list(ApplicationType))
    right_of_residence = fuzzy.FuzzyInteger(1, 1000000000)
    has_children = Faker("boolean")
    profile = factory.SubFactory(ProfileFactory)


class ApplicantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Applicant

    first_name = Faker("first_name")
    last_name = Faker("last_name")
    email = Faker("email")
    phone_number = Faker("phone_number")
    street_address = Faker("street_address")
    city = Faker("city")
    postal_code = Faker("postcode")
    date_of_birth = Faker("date_of_birth", minimum_age=18)
    age = LazyAttribute(lambda o: _calculate_age(o.date_of_birth))
    ssn_suffix = LazyAttribute(calculate_ssn_suffix)
    is_primary_applicant = Faker("boolean")
    application = factory.SubFactory(ApplicationFactory)


class ApplicationWithApplicantsFactory(ApplicationFactory):
    applicants_count = random.randint(1, 2)

    @factory.post_generation
    def applicants(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A count of applicants were passed, use it
            for n in range(extracted):
                ApplicantFactory(application=self)
        else:
            for n in range(self.applicants_count):
                ApplicantFactory(application=self)


class ApplicationApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApplicationApartment

    priority_number = fuzzy.FuzzyInteger(1, 5)
    apartment = factory.SubFactory(ApartmentFactory)
    application = factory.SubFactory(ApplicationWithApplicantsFactory)

    @classmethod
    def create_application_with_apartments(
        cls, apartments: List[ApartmentFactory], application: application
    ) -> List[ApplicationApartment]:

        apartments_application = []
        for i in range(len(apartments)):
            apartment_application = cls.create(
                priority_number=i + 1,
                apartment=apartments[i],
                application=application,
            )
            apartments_application.append(apartment_application)
        return apartments_application


class ApartmentReservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApartmentReservation

    apartment = factory.SubFactory(ApartmentFactory)
    queue_position = fuzzy.FuzzyInteger(1)
    application_apartment = factory.SubFactory(ApplicationApartmentFactory)
    state = fuzzy.FuzzyChoice(list(ApartmentReservationState))


class LotteryEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LotteryEvent

    apartment = factory.SubFactory(ApartmentFactory)


class LotteryEventResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LotteryEventResult

    event = factory.SubFactory(LotteryEventFactory)
    application_apartment = factory.SubFactory(ApplicationApartmentFactory)
    result_position = fuzzy.FuzzyInteger(1)
