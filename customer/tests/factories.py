"""
Factory classes for test purposes.
"""
from factory import django, Faker, SubFactory

from customer.models import Customer
from users.tests.factories import ProfileFactory


class CustomerFactory(django.DjangoModelFactory):
    """
    Factoring Customer information.
    """

    class Meta:
        model = Customer

    # Others
    additional_information = Faker("paragraph", nb_sentences=5)
    has_children = Faker("boolean")
    has_hitas_ownership = Faker("boolean")
    is_age_over_55 = Faker("boolean")
    is_right_of_occupancy_housing_changer = Faker("boolean")
    last_contact_date = Faker("date")
    primary_profile = SubFactory(ProfileFactory)
    right_of_residence = Faker("random_int", min=1, max=100000)
    right_of_residence_is_old_batch = False
