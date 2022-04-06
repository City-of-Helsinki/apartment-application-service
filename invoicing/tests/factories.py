import factory

from application_form.tests.factories import ApartmentReservationFactory

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import ApartmentInstallment, InstallmentBase, ProjectInstallmentTemplate


class InstallmentBaseFactory(factory.django.DjangoModelFactory):
    # Faker("random_element") cannot be used because it could generate non-unique values
    type = factory.Sequence(
        lambda n: list(InstallmentType)[n % len(list(InstallmentType))]
    )
    value = factory.Faker("random_int", min=1000, max=9999)
    account_number = factory.Faker("iban")

    class Meta:
        model = InstallmentBase
        abstract = True


class ProjectInstallmentTemplateFactory(InstallmentBaseFactory):
    project_uuid = factory.Faker("uuid4")
    unit = factory.Faker("random_element", elements=list(InstallmentUnit))
    percentage_specifier = factory.Faker(
        "random_element", elements=list(InstallmentPercentageSpecifier)
    )

    class Meta:
        model = ProjectInstallmentTemplate


class ApartmentInstallmentFactory(InstallmentBaseFactory):
    apartment_reservation = factory.SubFactory(ApartmentReservationFactory)
    invoice_number = factory.Faker(
        "pystr_format", string_format="#########", letters="1234567890"
    )
    reference_number = factory.Faker("uuid4")

    class Meta:
        model = ApartmentInstallment
