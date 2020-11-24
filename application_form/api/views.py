from rest_framework import viewsets

from application_form.api.serializers import HasoSerializer, HitasSerializer
from application_form.selectors import list_haso_applications, list_hitas_applications


class HasoApplicationViewSet(viewsets.ModelViewSet):
    # Handles all CRUD operations.
    queryset = list_haso_applications()
    serializer_class = HasoSerializer


class HitasApplicationViewSet(viewsets.ModelViewSet):
    # Handles all CRUD operations.
    queryset = list_hitas_applications()
    serializer_class = HitasSerializer
