import itertools
import logging
from datetime import datetime, time

from dateutil import parser
from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404, HttpResponse
from django.utils import timezone
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
    ApplicantMailingListExportService,
    ProjectLotteryResultExportService,
    XlsxSalesReportExportService,
)
from users.enums import UserKeyValueKeys
from users.models import UserKeyValue

_logger = logging.getLogger(__name__)


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


class ProjectExportApplicantsMailingListAPIView(APIView):
    export_first_in_queue = "first_in_queue"

    allowed_apartment_export_types = [
        ApartmentReservationState.RESERVED.value,  # export all reservers
        ApartmentReservationState.SOLD.value,  # export all who have bought
        export_first_in_queue,  # export reservers who are first in queue
    ]

    http_method_names = ["get"]

    def get(self, request, project_uuid, export_type):
        try:
            apartment_uuids = get_apartment_uuids(project_uuid)
            project = get_project(project_uuid)
        except ObjectDoesNotExist:
            raise NotFound()

        reservations = ApartmentReservation.objects.filter(
            apartment_uuid__in=apartment_uuids,
        )

        export_services = ApplicantMailingListExportService(reservations, export_type)
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


class SaleReportSelectedProjectsAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request):
        # get included projects
        included_project_uuids = UserKeyValue.objects.user_key_values(
            user=request.user,
            key=UserKeyValueKeys.INCLUDE_SALES_REPORT_PROJECT_UUID.value,
        ).values_list("value", flat=True)
        # return all projects until the user saves some
        if included_project_uuids.count() == 0:
            project_data = get_projects()
        else:
            # filter projects
            project_data = [
                project
                for project in get_projects()
                if project.project_uuid in included_project_uuids
            ]

        serializer = ProjectDocumentListSerializer(project_data, many=True)
        return Response(serializer.data)


class SaleReportAPIView(APIView):
    http_method_names = ["get"]

    def get(self, request):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        project_uuids = request.query_params.get("project_uuids")

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
        tz = timezone.get_default_timezone()
        if not start_date_obj.tzinfo:
            start_date_obj = start_date_obj.replace(tzinfo=tz)
        if not end_date_obj.tzinfo:
            end_date_obj = end_date_obj.replace(tzinfo=tz)

        state_events = ApartmentReservationStateChangeEvent.objects.filter(
            timestamp__range=[
                datetime.combine(start_date_obj, time.min),
                datetime.combine(end_date_obj, time.max),
            ],
            state=ApartmentReservationState.SOLD,
        )
        if project_uuids:
            project_uuids = set(project_uuids.split(","))

            # not the most efficient way, but good enough for the low user counts
            # use itertools to flatten the list of lists to a single one
            apartment_uuids = itertools.chain.from_iterable(
                get_apartment_uuids(uuid) for uuid in project_uuids
            )
            state_events = state_events.filter(
                reservation__apartment_uuid__in=apartment_uuids
            )

            # update list of sales report project uuids
            key_values = [
                UserKeyValue(
                    user=request.user,
                    key=UserKeyValueKeys.INCLUDE_SALES_REPORT_PROJECT_UUID.value,
                    value=project_uuid,
                )
                for project_uuid in project_uuids
            ]

            # use ignore_conflicts to "filter out" duplicate project_uuids when creating
            UserKeyValue.objects.bulk_create(key_values, ignore_conflicts=True)

            to_delete = set(p.project_uuid for p in get_projects()).difference(
                project_uuids
            )

            # delete project uuids that werent selected
            UserKeyValue.objects.user_key_values(
                user=request.user,
                key=UserKeyValueKeys.INCLUDE_SALES_REPORT_PROJECT_UUID.value,
            ).filter(value__in=to_delete).delete()

        _logger.debug(
            "User %s creating salesreport with params %s. Found %s state events",
            request.user,
            request.query_params,
            state_events.count(),
        )

        export_services = XlsxSalesReportExportService(state_events)
        xlsx_file = export_services.write_xlsx_file()
        file_name = format_lazy(
            _("Sale report {start_date} - {end_date}"),
            start_date=start_date,
            end_date=end_date,
        ).replace(" ", "_")

        response_content = xlsx_file.read()
        response = HttpResponse(
            response_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # noqa:E501
        )
        response[
            "Content-Disposition"
        ] = "attachment; filename={file_name}.xlsx".format(file_name=file_name)

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
