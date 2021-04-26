import logging
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ViewSet

# from rest_framework import status
# from rest_framework.decorators import action
# from rest_framework.response import Response

_logger = logging.getLogger(__name__)


class ConnectionsRPC(ViewSet):  # pragma: no cover
    """
    An RPC class for calling special prosedures via api.
    """

    permission_classes = (IsAuthenticated,)
