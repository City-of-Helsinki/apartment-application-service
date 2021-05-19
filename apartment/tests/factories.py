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

    id = uuid.uuid4()

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of groups were passed in, use them
            for identifier in extracted:
                self.identifiers.add(identifier)

        identifier = IdentifierFactory.create()
        self.identifiers.add(identifier)


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    id = uuid.uuid4()
    project = factory.SubFactory(ProjectFactory)
    is_available = True

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            # Simple build, do nothing.
            return

        if extracted:
            # A list of groups were passed in, use them
            for identifier in extracted:
                self.identifiers.add(identifier)

        identifier = IdentifierFactory.create()
        self.identifiers.add(identifier)

    @classmethod
    def create_batch_with_project(cls, size: int, project: Project) -> List[Apartment]:
        apartments = []
        for i in range(size):
            apartment = cls.create(is_available=True, project=project)
            apartments.append(apartment)
        return apartments
