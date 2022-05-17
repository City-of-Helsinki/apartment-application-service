from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apartment.api.serializers import (
    ApartmentDocumentSerializer,
    ProjectDocumentDetailSerializer,
    ProjectDocumentListSerializer,
)
from apartment.elastic.queries import (
    get_apartment_uuids,
    get_apartments,
    get_project,
    get_projects,
)
from application_form.models import ApartmentReservation
from application_form.services.export import ApplicantExportService


class ApartmentAPIView(APIView):
    permission_classes = [
        permissions.AllowAny,
    ]
    http_method_names = ["get"]

    def get(self, request):
        project_uuid = request.GET.get("project_uuid", None)
        apartments = get_apartments(project_uuid)
        serializer = ApartmentDocumentSerializer(apartments, many=True)
        return Response(serializer.data)


class ProjectAPIView(APIView):
    permission_classes = [
        permissions.AllowAny,
    ]
    http_method_names = ["get"]

    def get(self, request, project_uuid=None):
        many = project_uuid is None
        try:
            if not many:
                project_data = get_project(project_uuid)
            else:
                project_data = get_projects()
        except ObjectDoesNotExist:
            raise NotFound()
        serializer_class = (
            ProjectDocumentListSerializer if many else ProjectDocumentDetailSerializer
        )
        serializer = serializer_class(project_data, many=many)
        return Response(serializer.data)


class ProjectExportApplicantsAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    http_method_names = ["get"]

    def get(self, request, project_uuid):
        try:
            apartment_uuids = get_apartment_uuids(project_uuid)
            project = get_project(project_uuid)
        except ObjectDoesNotExist:
            raise NotFound()
        reservations = ApartmentReservation.objects.filter(
            apartment_uuid__in=apartment_uuids
        )
        export_services = ApplicantExportService(reservations)
        csv_file = export_services.get_csv_string()
        file_name = format_lazy(
            _("[Project {title}] Applicants information"),
            title=project.project_street_address,
        ).replace(" ", "_")
        response = HttpResponse(csv_file, content_type="text/csv")
        response["Content-Disposition"] = "attachment; filename={file_name}.csv".format(
            file_name=file_name
        )
        return response
