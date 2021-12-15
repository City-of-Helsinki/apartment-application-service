import pytest
from django.core.management import call_command

from connections.tests.utils import (
    get_elastic_apartments_for_sale_only_uuids,
    get_elastic_apartments_for_sale_published_uuids,
    get_elastic_apartments_not_for_sale,
    make_apartments_sold_in_elastic,
    publish_elastic_apartments,
)


@pytest.mark.usefixtures("client")
@pytest.mark.django_db
class TestConnectionsApis:
    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_get_mapped_apartments(self, api_client):
        expected = get_elastic_apartments_for_sale_published_uuids()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == expected

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_get_new_published_apartments(self, api_client):
        expected = get_elastic_apartments_for_sale_published_uuids()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert sorted(response.data) == sorted(expected)

        not_published = get_elastic_apartments_for_sale_only_uuids()
        expected_new = publish_elastic_apartments(
            not_published, publish_to_etuovi=True, publish_to_oikotie=True
        )

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response_new = api_client.get(
            "/v1/connections/get_mapped_apartments", follow=True
        )

        assert sorted(response_new.data) == sorted(expected_new)
        # new apartments are 3 from not published anywhere
        assert len(response_new.data) - len(response.data) == 3

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_apartments_for_sale_need_FOR_SALE_flag(self, api_client):
        expected = get_elastic_apartments_not_for_sale()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert set(expected) not in set(response.data)

    @pytest.mark.usefixtures(
        "not_sending_oikotie_ftp", "not_sending_etuovi_ftp", "elastic_apartments"
    )
    def test_no_mapped_apartments(self, api_client):
        """
        if no apartments are mapped should return empty list
        """
        make_apartments_sold_in_elastic()

        call_command("send_etuovi_xml_file")
        call_command("send_oikotie_xml_file")

        response = api_client.get("/v1/connections/get_mapped_apartments", follow=True)

        assert response.data == []
