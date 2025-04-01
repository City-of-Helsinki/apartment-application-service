from rest_framework import permissions, status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apartment.elastic.queries import get_apartment_uuids
from application_form.api.serializers import (
    ApartmentReservationSerializer,
    ApplicantSerializerBase,
    ApplicationSerializer,
)
from application_form.models import ApartmentReservation, Application
from application_form.services.application import delete_application
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

    serializer_class = ApplicantSerializerBase
    http_method_names = ["get"]

    def get(self, request, customer_id):
        try:
            application = Application.objects.filter(customer__id=customer_id).latest(
                "created_at"
            )
        except Application.DoesNotExist:
            application = None

        if application:
            applicant = application.applicants.filter(is_primary_applicant=True).first()
            if applicant:
                serializer = self.get_serializer(applicant)
                return Response(serializer.data)

        return Response({})


class DeleteApplicationView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, application_uuid):
        applications = Application.objects.filter(external_uuid=application_uuid)

        if not applications.exists():
            return Response(
                {"detail": "Application not found."}, status=status.HTTP_404_NOT_FOUND
            )

        applications = applications.filter(customer__primary_profile__user=request.user)

        if not applications.exists():
            return Response(
                {"detail": "You do not have permission to delete this application."},
                status=status.HTTP_403_FORBIDDEN,
            )

        application = applications.order_by("-created_at").first()

        delete_application(application)
        return Response(status=status.HTTP_204_NO_CONTENT)
