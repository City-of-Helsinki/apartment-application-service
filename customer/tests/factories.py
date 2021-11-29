"""
Factory classes for test purposes.
"""
from factory import django, Faker, post_generation

from customer.models import Customer


class CustomerFactory(django.DjangoModelFactory):
    """
    Factoring Customer information.
    """

    class Meta:
        model = Customer

    # Others
    additional_information = Faker("paragraph", nb_sentences=5)
    last_contact_date = Faker("date")

    @post_generation
    def profiles(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for profile in extracted:
                self.profiles.add(profile)
