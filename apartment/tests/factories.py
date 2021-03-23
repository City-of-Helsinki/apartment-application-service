import factory
import uuid

from apartment.models import Apartment


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    apartment_uuid = factory.Sequence(lambda n: "%s" % uuid.uuid4())
    is_available = True
