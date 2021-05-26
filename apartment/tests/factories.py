import factory
import uuid
from factory import fuzzy
from typing import List

from apartment.enums import IdentifierSchemaType
from apartment.models import Apartment, Identifier, IdentifierSchema, Project


class IdentifierSchemaFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = IdentifierSchema
        django_get_or_create = ("schema_type",)

    schema_type = fuzzy.FuzzyChoice(list(IdentifierSchemaType))


class IdentifierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Identifier

    schema = factory.SubFactory(IdentifierSchemaFactory)
    identifier = factory.Sequence(lambda n: "%s" % uuid.uuid4())


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    id = factory.Faker("uuid4")

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of identifier were passed in, use them
            for identifier in extracted:
                self.identifiers.add(identifier)
        else:
            identifier = IdentifierFactory.create()
            self.identifiers.add(identifier)


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    id = factory.Faker("uuid4")
    project = factory.SubFactory(ProjectFactory)
    is_available = True

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for identifier in extracted:
                self.identifiers.add(identifier)

        identifier = IdentifierFactory.create()
        self.identifiers.add(identifier)

    @classmethod
    def create_batch_with_project(cls, size: int, project=None) -> List[Apartment]:
        if project is None:
            project = cls.project

        apartments = []
        for i in range(size):
            apartment = cls.create(id=uuid.uuid4(), is_available=True, project=project)
            apartments.append(apartment)
        return apartments
