import pytest
from django.core.management import call_command

from connections.tests.utils import (
    get_elastic_apartments_for_sale_uuids,
    make_apartments_sold_in_elastic,
)


@pytest.mark.usefixtures("client", "elastic_apartments")
@pytest.mark.django_db
class TestConnectionsApis:
    @pytest.mark.usefixtures("not_sending_oikotie_ftp", "not_sending_etuovi_ftp")
    def test_get_mapped_apartments(self, api_client):
        expected = get_elastic_apartments_for_sale_uuids()
        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == expected

    @pytest.mark.usefixtures("not_sending_oikotie_ftp", "not_sending_etuovi_ftp")
    def test_no_mapped_apartments(self, api_client):
        """
        if no apartments are mapped should return empty list
        """
        make_apartments_sold_in_elastic()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == []
