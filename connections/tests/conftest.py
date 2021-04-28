from django.contrib.auth.models import Permission
from elasticsearch.helpers.test import get_test_client, SkipTest
from elasticsearch_dsl.connections import add_connection
from pytest import fixture, skip
from rest_framework.test import APIClient
from time import sleep

from application_form.tests.factories import UserFactory
from connections.tests.factories import ApartmentMinimalFactory


@fixture
def api_client():
    user = UserFactory()
    permissions = Permission.objects.all()
    user.user_permissions.set(permissions)
    api_client = APIClient()
    api_client.force_authenticate(user)
    return api_client


@fixture(scope="class")
def client():
    try:
        connection = get_test_client()
        add_connection("default", connection)
        yield connection
        connection.indices.delete("test-*", ignore=404)
    except SkipTest:
        skip()


@fixture(scope="class")
def elastic_apartments():
    try:
        elastic_apartments = ApartmentMinimalFactory.create_batch(20)
        for item in elastic_apartments:
            item.save()
        sleep(3)
        yield elastic_apartments
    except SkipTest:
        skip()


@fixture()
def broken_elastic_apartments_for_sale():
    # oikotie broken data is in project_new_development_status
    # etuovi broken data is in project_building_type
    elastic_apartment_1 = ApartmentMinimalFactory.build(
        project_new_development_status="rakenteilla",
        project_building_type="rivitalo",
        apartment_state_of_sale="FOR_SALE",
        _language="fi",
    )
    elastic_apartment_2 = ApartmentMinimalFactory.build(
        project_new_development_status="suunnitteilla",
        project_building_type="kerrostalo",
        apartment_state_of_sale="FOR_SALE",
        _language="fi",
    )
    for item in [elastic_apartment_1, elastic_apartment_2]:
        item.save()
    sleep(3)
    yield elastic_apartments
