import logging

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from connections.api.serializers import MappedApartmentSerializer
from connections.models import MappedApartment

_logger = logging.getLogger(__name__)


class Connections(ModelViewSet):
    """
    A class for for internal communication with Drupal.
    """

    queryset = MappedApartment.objects.all()
    serializer_class = MappedApartmentSerializer
    permission_classes = (IsAuthenticatedOrReadOnly,)

    @action(methods=["get"], detail=False, url_path="get_mapped_apartments")
    def get_mapped_apartments(self, request):
        apartment_uuids = MappedApartment.objects.filter(
            mapped_etuovi=True, mapped_oikotie=True
        ).values_list("apartment_uuid", flat=True)
        apartment_uuids = [str(i) for i in apartment_uuids]

        return Response(
            apartment_uuids,
            content_type="application/json",
            status=status.HTTP_200_OK,
        )
