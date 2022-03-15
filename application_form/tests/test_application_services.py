import pytest
from datetime import date

from application_form.enums import ApplicationType
from application_form.services.application import (
    create_application,
    get_ordered_applications,
)
from application_form.tests.conftest import create_validated_application_data
from users.tests.factories import ProfileFactory


@pytest.mark.django_db
@pytest.mark.parametrize("num_applicants", [1, 2])
def test_create_application(num_applicants, elastic_single_project_with_apartments):
    profile = ProfileFactory()
    data = create_validated_application_data(
        profile, ApplicationType.HASO, num_applicants
    )
    application = create_application(data)

    # A new application should have been created
    assert application.external_uuid == data["external_uuid"]
    assert application.applicants_count == num_applicants
    assert application.applicants.count() == num_applicants
    assert application.type.value == data["type"].value
    assert application.right_of_residence == data["right_of_residence"]
    assert application.has_children == data["has_children"]
    assert application.customer.primary_profile == profile
    assert application.application_apartments.count() == 5

    # The application should have linked apartments for each priority number
    for apartment_data in data["apartments"]:
        application_apartments = application.application_apartments.filter(
            apartment_uuid=apartment_data["identifier"],
        )
        assert application_apartments.count() == 1

    # The application should always have a primary applicant
    assert application.applicants.filter(is_primary_applicant=True).count() == 1
    applicant1 = application.applicants.get(is_primary_applicant=True)
    assert applicant1.first_name == profile.first_name
    assert applicant1.last_name == profile.last_name
    assert applicant1.email == profile.email
    assert applicant1.phone_number == profile.phone_number
    assert applicant1.street_address == profile.street_address
    assert applicant1.city == profile.city
    assert applicant1.postal_code == profile.postal_code
    assert applicant1.age in (
        date.today().year - profile.date_of_birth.year,
        date.today().year - profile.date_of_birth.year - 1,
    )

    # The application may have an additional applicant
    if num_applicants == 2:
        assert application.applicants.filter(is_primary_applicant=False).count() == 1
        applicant2 = application.applicants.get(is_primary_applicant=False)
        assert applicant2.first_name == data["additional_applicant"]["first_name"]
        assert applicant2.last_name == data["additional_applicant"]["last_name"]
        assert applicant2.email == data["additional_applicant"]["email"]
        assert applicant2.phone_number == data["additional_applicant"]["phone_number"]
        assert (
            applicant2.street_address == data["additional_applicant"]["street_address"]
        )
        assert applicant2.city == data["additional_applicant"]["city"]
        assert applicant2.postal_code == data["additional_applicant"]["postal_code"]
        assert applicant2.age in (
            date.today().year - data["additional_applicant"]["date_of_birth"].year,
            date.today().year - data["additional_applicant"]["date_of_birth"].year - 1,
        )


@pytest.mark.django_db
@pytest.mark.parametrize("application_type", list(ApplicationType))
def test_create_application_type(
    application_type, elastic_single_project_with_apartments
):
    profile = ProfileFactory()
    data = create_validated_application_data(profile, application_type)
    application = create_application(data)
    assert application.type == application_type


@pytest.mark.django_db
def test_create_application_adds_haso_application_to_queue_by_right_of_residence(
    elastic_single_project_with_apartments,
):
    data = create_validated_application_data(ProfileFactory(), ApplicationType.HASO)
    application2 = create_application({**data, "right_of_residence": 2})
    application1 = create_application({**data, "right_of_residence": 1})
    for application_apartment in application1.application_apartments.all():
        assert list(get_ordered_applications(application_apartment.apartment_uuid)) == [
            application1,
            application2,
        ]


@pytest.mark.django_db
def test_create_application_adds_hitas_application_to_queue_by_application_order(
    elastic_single_project_with_apartments,
):
    data = create_validated_application_data(ProfileFactory(), ApplicationType.HITAS)
    application2 = create_application({**data, "right_of_residence": 2})
    application1 = create_application({**data, "right_of_residence": 1})
    for application_apartment in application1.application_apartments.all():
        assert list(get_ordered_applications(application_apartment.apartment_uuid)) == [
            application2,
            application1,
        ]
