import factory

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import ApartmentInstallment, InstallmentBase, ProjectInstallmentTemplate


class InstallmentBaseFactory(factory.django.DjangoModelFactory):
    type = factory.Faker("random_element", elements=list(InstallmentType))
    value = factory.Faker("random_int", min=1000, max=9999)
    unit = factory.Faker("random_element", elements=list(InstallmentUnit))
    percentage_specifier = factory.Faker(
        "random_element", elements=list(InstallmentPercentageSpecifier)
    )
    account_number = factory.Faker("iban")

    class Meta:
        model = InstallmentBase
        abstract = True


class ProjectInstallmentTemplateFactory(InstallmentBaseFactory):
    project_uuid = factory.Faker("uuid4")

    class Meta:
        model = ProjectInstallmentTemplate


class ApartmentInstallmentFactory(InstallmentBaseFactory):
    apartment_uuid = factory.Faker("uuid4")
    reference_number = factory.Faker("uuid4")

    class Meta:
        model = ApartmentInstallment
