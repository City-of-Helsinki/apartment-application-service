from rest_framework import viewsets
from rest_framework.permissions import DjangoModelPermissions

from application_form.api.serializers import HasoSerializer, HitasSerializer
from application_form.selectors import list_haso_applications, list_hitas_applications


class HasoApplicationViewSet(viewsets.ModelViewSet):
    # Handles all CRUD operations.
    queryset = list_haso_applications()
    serializer_class = HasoSerializer
    permission_classes = [DjangoModelPermissions]


class HitasApplicationViewSet(viewsets.ModelViewSet):
    # Handles all CRUD operations.
    queryset = list_hitas_applications()
    serializer_class = HitasSerializer
    permission_classes = [DjangoModelPermissions]
