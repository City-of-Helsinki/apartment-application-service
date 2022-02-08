from rest_framework import mixins, permissions, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from apartment.elastic.queries import get_apartment_uuids
from application_form.api.sales.serializers import RootApartmentReservationSerializer
from application_form.api.serializers import (
    ApartmentReservationSerializer,
    ApplicationSerializer,
)
from application_form.models import ApartmentReservation, Application
from audit_log.viewsets import AuditLoggingModelViewSet


class ApplicationViewSet(AuditLoggingModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "external_uuid"
    http_method_names = ["post"]


class ListProjectReservations(GenericAPIView):
    """
    Public: Returns a list of the user's apartment reservations from a specific project.
    """

    serializer_class = ApartmentReservationSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request, project_uuid):
        apartment_uuid_list = get_apartment_uuids(project_uuid)
        profile_uuid = request.user.profile.id
        reservations = ApartmentReservation.objects.filter(
            apartment_uuid__in=apartment_uuid_list,
            application_apartment__application__profile__id=profile_uuid,
        )
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)


class ApartmentReservationViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ApartmentReservation.objects.all()
    serializer_class = RootApartmentReservationSerializer
    permission_classes = [permissions.AllowAny]
