import pytest

from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate
from invoicing.tests.factories import (
    ApartmentInstallmentFactory,
    ProjectInstallmentTemplateFactory,
)


@pytest.mark.django_db
def test_project_installment_template_factory_creation():
    ProjectInstallmentTemplateFactory()
    assert ProjectInstallmentTemplate.objects.count() == 1


@pytest.mark.django_db
def test_apartment_installment_factory_creation():
    ApartmentInstallmentFactory()
    assert ApartmentInstallment.objects.count() == 1
