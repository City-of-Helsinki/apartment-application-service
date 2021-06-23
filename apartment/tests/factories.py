import factory
import uuid
from factory import Faker, fuzzy
from string import ascii_letters, digits
from typing import List

from apartment.enums import IdentifierSchemaType
from apartment.models import Apartment, Identifier, Project


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    street_address = Faker("street_address")

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for identifier in extracted:
                IdentifierFactory.create(
                    identifier=identifier, project=self, apartment=None
                )
        else:
            identifier = IdentifierFactory.create(project=self, apartment=None)
            self.identifiers.add(identifier)


class ApartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Apartment

    street_address = Faker("street_address")
    apartment_number = fuzzy.FuzzyText(length=3, chars=ascii_letters + digits)
    project = factory.SubFactory(ProjectFactory)

    @factory.post_generation
    def identifiers(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            for identifier in extracted:
                self.identifiers.add(
                    IdentifierFactory.create(
                        identifier=identifier, apartment=self, project=None
                    )
                )

        else:
            identifier = IdentifierFactory.create(apartment=self, project=None)
            self.identifiers.add(identifier)

    @classmethod
    def create_batch_with_project(
        cls, size: int, project=None, identifier_schema="att"
    ) -> List[Apartment]:
        if project is None:
            project = cls.project
        if identifier_schema == "att":
            identifiers = [
                IdentifierFactory(
                    identifier=factory.Sequence(lambda n: "%s" % uuid.uuid4()),
                    schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
                    apartment=None,
                    project=None,
                )
            ]

        apartments = []
        for i in range(size):
            apartment = cls.create(identifiers=identifiers, project=project)
            apartments.append(apartment)
        return apartments


class IdentifierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Identifier
        django_get_or_create = ("identifier",)

    schema_type = fuzzy.FuzzyChoice(list(IdentifierSchemaType))
    identifier = fuzzy.FuzzyText(length=36)
    project = factory.SubFactory(ProjectFactory)
    apartment = factory.SubFactory(ApartmentFactory)

    @classmethod
    def build_batch_for_att_schema(cls, size: int, uuids_list: list):
        return [
            cls.build(
                identifier=uuids_list[i],
                schema_type=IdentifierSchemaType.ATT_PROJECT_ES,
            )
            for i in range(size)
        ]
