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
    last_contact_date = Faker("date")
    primary_profile = SubFactory(ProfileFactory)
