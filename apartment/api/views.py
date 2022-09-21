from dateutil import parser
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import RetrieveUpdateAPIView
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
from apartment.models import ProjectExtraData
from application_form.api.sales.serializers import (
    ProjectExtraDataSerializer,
    SalesApartmentReservationSerializer,
)
from application_form.enums import ApartmentReservationState
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    LotteryEvent,
)
from application_form.services.export import (
    ApplicantExportService,
    ProjectLotteryResultExportService,
    SaleReportExportService,
)


class ApartmentAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request):
        project_uuid = request.GET.get("project_uuid", None)
        apartments = get_apartments(project_uuid)
        serializer = ApartmentDocumentSerializer(apartments, many=True)
        return Response(serializer.data)


class ApartmentReservationsAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request, apartment_uuid):
        serializer = SalesApartmentReservationSerializer(
            ApartmentReservation.objects.related_fields()
            .filter(apartment_uuid=apartment_uuid)
            .order_by("list_position"),
            many=True,
        )
        return Response(serializer.data)


class ProjectAPIView(APIView):
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
        response = HttpResponse(csv_file, content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = "attachment; filename={file_name}.csv".format(
            file_name=file_name
        )
        return response


class ProjectExportLotteryResultsAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request, project_uuid):
        try:
            apartment_uuids = get_apartment_uuids(project_uuid)
            project = get_project(project_uuid)
        except ObjectDoesNotExist:
            raise NotFound()
        if LotteryEvent.objects.filter(apartment_uuid__in=apartment_uuids).count() == 0:
            raise ValidationError("Project lottery has not happened yet")
        export_services = ProjectLotteryResultExportService(project)
        csv_file = export_services.get_csv_string()
        file_name = format_lazy(
            _("[Project {title}] Lottery result"),
            title=project.project_street_address,
        ).replace(" ", "_")
        response = HttpResponse(csv_file, content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = "attachment; filename={file_name}.csv".format(
            file_name=file_name
        )
        return response


class SaleReportAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date is None or end_date is None:
            raise ValidationError("Missing start date or end date")
        try:
            start_date_obj = parser.isoparse(start_date)
            end_date_obj = parser.isoparse(end_date)
        except ValueError:
            raise ValidationError(
                "Invalid datetime format, "
                "the correct format is - `YYYY-MM-DD` or `YYYYMMDD`"
            )
        if start_date_obj > end_date_obj:
            raise ValidationError("Start date cannot be greater than end date")
        state_events = ApartmentReservationStateChangeEvent.objects.filter(
            timestamp__range=[start_date_obj, end_date_obj],
            state=ApartmentReservationState.SOLD,
        )
        export_services = SaleReportExportService(state_events)
        csv_file = export_services.get_csv_string()
        file_name = format_lazy(
            _("Sale report {start_date} - {end_date}"),
            start_date=start_date,
            end_date=end_date,
        ).replace(" ", "_")
        response = HttpResponse(csv_file, content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = "attachment; filename={file_name}.csv".format(
            file_name=file_name
        )
        return response


class ProjectExtraDataAPIView(RetrieveUpdateAPIView):
    queryset = ProjectExtraData.objects.all()
    serializer_class = ProjectExtraDataSerializer
    lookup_field = "project_uuid"

    def get_object(self):
        try:
            get_project(self.kwargs["project_uuid"])
        except ObjectDoesNotExist as e:
            raise NotFound(e)
        try:
            return super().get_object()
        except Http404:
            # When the ProjectExtraData instance does not exist already, this works for
            # both retrieve and update:
            #   * when retrieving, we want to return the object same kind of object with
            #     fields empty rather than 404
            #   * when updating, we want to create the ProjectExtraData instance if it
            #     doesn't exist already.
            return ProjectExtraData(project_uuid=self.kwargs["project_uuid"])
