import logging

from rest_framework.viewsets import ViewSet
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status

from connections.etuovi.services import (
    fetch_apartments as etuovi_fetch_apartments,
    create_xml,
)


_logger = logging.getLogger(__name__)


class ConnectionsRPC(ViewSet):
    """
    An RPC class for calling special prosedures via api for testing.
    """

    @action(methods=["get"], detail=False, url_path="create_etuovi_xml")
    def create_etuovi_xml(self, request):
        items = etuovi_fetch_apartments()
        if create_xml(items):
            return Response(
                f"Fetched {len(items)} apartements for XML file",
                status=status.HTTP_200_OK,
            )
        else:
            return Response("Etuovi XML not created", status=status.HTTP_200_OK)
