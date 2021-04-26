import logging
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from connections.etuovi.services import create_xml as etuovi_create_xml
from connections.etuovi.services import (
    fetch_apartments_for_sale as etuovi_fetch_apartments,
)
from connections.oikotie.services import (
    create_xml_apartment_file as oikotie_create_apartment_xml,
)
from connections.oikotie.services import (
    create_xml_housing_company_file as oikotie_create_housing_company_xml,
)
from connections.oikotie.services import (
    fetch_apartments_for_sale as oikotie_fetch_apartments,
)
from connections.utils import create_elastic_connection

_logger = logging.getLogger(__name__)


class ConnectionsRPC(ViewSet):  # pragma: no cover
    """
    An RPC class for calling special prosedures via api.
    """

    permission_classes = (IsAuthenticated,)

    create_elastic_connection()

    @action(methods=["get"], detail=False, url_path="create_etuovi_xml")
    def create_etuovi_xml(self, request):
        items = etuovi_fetch_apartments()
        if etuovi_create_xml(items):
            return Response(
                f"Fetched {len(items)} apartements for XML file",
                status=status.HTTP_200_OK,
            )
        else:
            return Response("Etuovi XML not created", status=status.HTTP_200_OK)

    @action(methods=["get"], detail=False, url_path="create_oikotie_xml")
    def create_oikotie_xml(self, request):
        apartments, housing_companies = oikotie_fetch_apartments()
        if oikotie_create_apartment_xml(
            apartments
        ) and oikotie_create_housing_company_xml(housing_companies):
            return Response(
                f"Fetched {len(apartments)} apartements for XML file",
                status=status.HTTP_200_OK,
            )
        else:
            return Response("Apartment XML not created", status=status.HTTP_200_OK)
