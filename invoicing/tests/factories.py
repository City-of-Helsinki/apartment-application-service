import factory
import faker

from application_form.tests.factories import ApartmentReservationFactory

from ..enums import InstallmentPercentageSpecifier, InstallmentType, InstallmentUnit
from ..models import (
    ApartmentInstallment,
    InstallmentBase,
    Payment,
    PaymentBatch,
    ProjectInstallmentTemplate,
)

unique_number_faker = faker.Faker()


class InstallmentBaseFactory(factory.django.DjangoModelFactory):
    # Faker("random_element") cannot be used because it could generate non-unique values
    # Might be necessary to call InstallmentBaseFactory.reset_sequence(0)
    # at the start of test cases
    # if you are running into issues with tests only failing when ran alongside other tests  # noqa: E501
    type = factory.Sequence(
        lambda n: list(InstallmentType)[n % len(list(InstallmentType))]
    )
    value = factory.Faker("random_int", min=1000, max=9999)
    account_number = factory.Faker("iban")
    due_date = factory.Faker("future_date")

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

    # Use MAX_INVOICE_NUMBER - 100 to leave some leeway for tests
    invoice_number = factory.Sequence(
        lambda _: unique_number_faker.unique.random_int(
            min=ApartmentInstallment.MIN_INVOICE_NUMBER,
            max=ApartmentInstallment.MAX_INVOICE_NUMBER - 100,
        )
    )
    reference_number = factory.Faker("uuid4")
    handler = factory.Faker("name")

    class Meta:
        model = ApartmentInstallment


class PaymentBatchFactory(factory.django.DjangoModelFactory):
    filename = factory.Sequence(lambda n: f"TEST_PAYMENTS_{n}.txt")

    class Meta:
        model = PaymentBatch


class PaymentFactory(factory.django.DjangoModelFactory):
    batch = factory.SubFactory(PaymentBatchFactory)
    apartment_installment = factory.SubFactory(ApartmentInstallmentFactory)
    amount = factory.Faker("random_int", min=100, max=999)
    payment_date = factory.Faker("past_date")

    class Meta:
        model = Payment
