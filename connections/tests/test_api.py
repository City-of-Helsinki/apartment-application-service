import os
import pytest
from django.core.management import call_command
from unittest import mock

from connections.etuovi.services import (
    fetch_apartments_for_sale as fetch_etuovi_apartments,
)
from connections.oikotie.services import (
    fetch_apartments_for_sale as fetch_oikotie_apartments,
)
from connections.tests.utils import (
    get_elastic_apartments_for_sale_uuids,
    make_apartments_sold_in_elastic,
)


@pytest.mark.usefixtures("client", "elastic_apartments")
@mock.patch.dict(os.environ, {"ENV": "dev"}, clear=True)
@pytest.mark.django_db
class TestConnectionsApis:
    def test_get_mapped_apartments(self, api_client):
        expected = get_elastic_apartments_for_sale_uuids()
        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")
        fetch_etuovi_apartments()
        fetch_oikotie_apartments()

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == expected

    def test_no_mapped_apartments(self, api_client):
        """
        if no apartments are mapped should return empty list
        """
        make_apartments_sold_in_elastic()

        fetch_etuovi_apartments()
        fetch_oikotie_apartments()

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == []

    @pytest.mark.usefixtures("not_sending_oikotie_ftp", "not_sending_etuovi_ftp")
    def test_mapped_apartments_removed_from_database(self, api_client):
        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")
        call_command("empty_mapped_apartments_database")
        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == []
