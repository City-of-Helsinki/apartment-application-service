import factory
import uuid
from django.contrib.auth import get_user_model
from factory import fuzzy

from application_form.models import (
    Apartment,
    CURRENT_HOUSING_CHOICES,
    HasoApartmentPriority,
    HasoApplication,
    HitasApplication,
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: "user_%d" % (n + 1))


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    apartment_uuid = factory.Sequence(lambda n: "%s" % uuid.uuid4())
    is_available = True


class HasoApartmentPriorityFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HasoApartmentPriority

    is_active = True
    priority_number = factory.Sequence(lambda n: "%d" % n)
    apartment = factory.SubFactory(ApartmentFactory)


class HasoApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HasoApplication

    is_approved = False
    is_rejected = False
    applicant_has_accepted_offer = False
    rejection_description = ""
    applicant_token = fuzzy.FuzzyText()
    right_of_occupancy_id = fuzzy.FuzzyInteger(0, 99999999)
    current_housing = fuzzy.FuzzyChoice([c[0] for c in CURRENT_HOUSING_CHOICES])
    housing_description = fuzzy.FuzzyText()
    housing_type = fuzzy.FuzzyText()
    housing_area = fuzzy.FuzzyFloat(0, 1000)
    is_changing_occupancy_apartment = True
    is_over_55 = True
    haso_apartment_priorities = factory.RelatedFactoryList(
        HasoApartmentPriorityFactory, factory_related_name="haso_application", size=5
    )

    @classmethod
    def create_batch_with_apartments(cls, size: int, apartments: list) -> list:
        applications = []
        for i in range(size):
            haso_application = cls.create(
                right_of_occupancy_id=i,
                is_approved=True,
                haso_apartment_priorities=None,
            )
            HasoApartmentPriorityFactory.create_batch(
                len(apartments),
                haso_application=haso_application,
                apartment=factory.Iterator(apartments),
            )
            applications.append(haso_application)
        return applications


class HitasApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = HitasApplication

    is_approved = False
    is_rejected = False
    applicant_has_accepted_offer = False
    rejection_description = ""
    applicant_token = fuzzy.FuzzyText()
    has_previous_hitas_apartment = True
    previous_hitas_description = fuzzy.FuzzyText()
    has_children = True
    apartment = factory.SubFactory(ApartmentFactory)
