from rest_framework import permissions, status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from apartment.elastic.queries import get_apartment_uuids
from application_form.api.serializers import ApartmentReservationSerializer
from application_form.api.serializers import (
    ApplicantSerializerBase as ApplicantSerializer,
)
from application_form.api.serializers import ApplicationSerializer
from application_form.models import ApartmentReservation, Application
from audit_log.viewsets import AuditLoggingModelViewSet


class ApplicationViewSet(AuditLoggingModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "external_uuid"
    http_method_names = ["post"]


class ListProjectReservations(GenericAPIView):
    """
    Public: Returns a list of the user's apartment reservations from a specific project.
    """

    serializer_class = ApartmentReservationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get"]

    def get(self, request, project_uuid):
        apartment_uuid_list = get_apartment_uuids(project_uuid)
        profile_uuid = request.user.profile.id
        reservations = ApartmentReservation.objects.filter(
            apartment_uuid__in=apartment_uuid_list,
            application_apartment__application__customer__primary_profile__id=profile_uuid,  # noqa
        )
        serializer = self.get_serializer(reservations, many=True)
        return Response(serializer.data)


class LatestApplicantInfo(GenericAPIView):
    """
    Returns the primary applicant from the latest application.
    """

    serializer_class = ApplicantSerializer
    http_method_names = ["get"]

    def get(self, request, customer_id):
        try:
            application = Application.objects.filter(customer__id=customer_id).latest(
                "created_at"
            )
            applicant = application.applicants.filter(is_primary_applicant=True).first()
            if applicant:
                serializer = self.get_serializer(applicant)
                return Response(serializer.data)
            return Response(
                {"err": "No primary applicant found"}, status.HTTP_404_NOT_FOUND
            )
        except Application.DoesNotExist:
            return Response(
                {"error": "No application found"}, status.HTTP_404_NOT_FOUND
            )
