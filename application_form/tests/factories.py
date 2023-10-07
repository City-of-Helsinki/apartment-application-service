import random
import uuid
from datetime import timedelta
from typing import List

import factory
from django.utils import timezone
from factory import Faker, fuzzy, LazyAttribute

from apartment_application_service.settings import (
    METADATA_HANDLER_INFORMATION,
    METADATA_HASO_PROCESS_NUMBER,
    METADATA_HITAS_PROCESS_NUMBER,
)
from application_form.enums import ApartmentReservationState, ApplicationType
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    Applicant,
    Application,
    ApplicationApartment,
    LotteryEvent,
    LotteryEventResult,
    Offer,
)
from application_form.services.application import _calculate_age
from application_form.tests.utils import calculate_ssn_suffix
from customer.tests.factories import CustomerFactory
from users.tests.factories import UserFactory


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application

    external_uuid = factory.Faker("uuid4")
    applicants_count = fuzzy.FuzzyInteger(1, 2)
    type = fuzzy.FuzzyChoice(list(ApplicationType))
    right_of_residence = fuzzy.FuzzyInteger(1, 100000)
    right_of_residence_is_old_batch = False
    has_children = Faker("boolean")
    customer = factory.SubFactory(CustomerFactory)
    handler_information = METADATA_HANDLER_INFORMATION
    process_number = fuzzy.FuzzyChoice(
        [METADATA_HITAS_PROCESS_NUMBER, METADATA_HASO_PROCESS_NUMBER]
    )
    sender_names = Faker("name")


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
    ssn_suffix = LazyAttribute(lambda o: calculate_ssn_suffix(o.date_of_birth))
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
    apartment_uuid = factory.Faker("uuid4")
    application = factory.SubFactory(ApplicationWithApplicantsFactory)

    @classmethod
    def create_application_with_apartments(
        cls, apartment_uuids: List[uuid.UUID], application: application
    ) -> List[ApplicationApartment]:

        apartments_application = []
        for i in range(len(apartment_uuids)):
            apartment_application = cls.create(
                priority_number=i + 1,
                apartment_uuid=apartment_uuids[i],
                application=application,
            )
            apartments_application.append(apartment_application)
        return apartments_application


class ApartmentReservationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApartmentReservation

    apartment_uuid = factory.Faker("uuid4")
    customer = factory.SubFactory(CustomerFactory)
    queue_position = fuzzy.FuzzyInteger(1)
    list_position = fuzzy.FuzzyInteger(1)
    application_apartment = factory.SubFactory(ApplicationApartmentFactory)
    state = fuzzy.FuzzyChoice(list(ApartmentReservationState))
    right_of_residence = LazyAttribute(
        lambda o: o.application_apartment.application.right_of_residence
        if o.application_apartment
        else o.customer.right_of_residence
    )
    right_of_residence_is_old_batch = LazyAttribute(
        lambda o: o.application_apartment.application.right_of_residence_is_old_batch
        if o.application_apartment
        else o.customer.right_of_residence_is_old_batch
    )
    handler = factory.Faker("name")


class LotteryEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LotteryEvent

    apartment_uuid = factory.Faker("uuid4")
    handler = factory.Faker("name")


class LotteryEventResultFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LotteryEventResult

    event = factory.SubFactory(LotteryEventFactory)
    application_apartment = factory.SubFactory(ApplicationApartmentFactory)
    result_position = fuzzy.FuzzyInteger(1)


class ApartmentReservationStateChangeEventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ApartmentReservationStateChangeEvent

    reservation = factory.SubFactory(ApartmentReservationFactory)
    state = fuzzy.FuzzyChoice(list(ApartmentReservationState))
    user = factory.SubFactory(UserFactory)


class OfferFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Offer

    apartment_reservation = factory.SubFactory(ApartmentReservationFactory)
    comment = fuzzy.FuzzyText()
    valid_until = fuzzy.FuzzyDate(
        start_date=timezone.localdate() + timedelta(days=7),
        end_date=timezone.localdate() + timedelta(days=14),
    )
    handler = factory.Faker("name")
