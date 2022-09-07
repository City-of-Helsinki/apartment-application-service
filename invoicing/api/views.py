from django.db import transaction
from django.http import Http404, HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apartment.elastic.queries import get_apartment
from application_form.models import ApartmentReservation
from audit_log import audit_logging
from audit_log.enums import Operation

from ..api.serializers import (
    ApartmentInstallmentSerializer,
    ProjectInstallmentTemplateSerializer,
)
from ..enums import InstallmentType
from ..models import (
    AlreadyAddedToBeSentToSapError,
    ApartmentInstallment,
    ProjectInstallmentTemplate,
)
from ..pdf import create_invoice_pdf_from_installments


class InstallmentAPIViewBase(generics.ListCreateAPIView):
    parent_field: str

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(**{self.parent_field: self.kwargs[self.parent_field]})
            .order_by("id")
        )

    def get_serializer(self, *args, **kwargs):
        # this is required to be able to create a list of objects
        kwargs["many"] = True
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        serializer.context.update({"old_instances": self.get_queryset()})
        serializer.save(
            **{
                self.parent_field: self.kwargs[self.parent_field],
            }
        )


class ProjectInstallmentTemplateAPIView(InstallmentAPIViewBase):
    queryset = ProjectInstallmentTemplate.objects.all()
    serializer_class = ProjectInstallmentTemplateSerializer
    parent_field = "project_uuid"


class ApartmentInstallmentAPIView(InstallmentAPIViewBase):
    queryset = ApartmentInstallment.objects.all()
    serializer_class = ApartmentInstallmentSerializer
    parent_field = "apartment_reservation_id"


@extend_schema(
    description="Create an invoice PDF based on apartment installments.",
    parameters=[
        OpenApiParameter(
            name="index",
            description="Comma-separated installment types.",
            type={"type": "array", "items": {"type": "string"}},
            location=OpenApiParameter.QUERY,
            required=False,
        )
    ],
    responses={(200, "application/pdf"): OpenApiTypes.BINARY},
)
class ApartmentInstallmentInvoiceAPIView(APIView):
    def get(self, request, **kwargs):
        reservation = get_object_or_404(
            ApartmentReservation, pk=kwargs["apartment_reservation_id"]
        )
        installments = ApartmentInstallment.objects.filter(
            apartment_reservation_id=reservation.id
        ).order_by("id")

        if type_params := request.query_params.get("types"):
            types = [e for e in InstallmentType if e.value in type_params.split(",")]
            installments = installments.filter(type__in=types)

        if not installments.exists():
            raise Http404

        pdf_data = create_invoice_pdf_from_installments(installments)
        apartment = get_apartment(reservation.apartment_uuid)
        title = (apartment.title or "").strip().lower().replace(" ", "_")
        filename = f"laskut_{title}.pdf" if title else "laskut.pdf"

        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={filename}"

        return response


@extend_schema(
    description="Add apartment installments to be sent to SAP.",
    parameters=[
        OpenApiParameter(
            name="types",
            description="Comma-separated installment types.",
            type={"type": "array", "items": {"type": "string"}},
            location=OpenApiParameter.QUERY,
            required=False,
        )
    ],
)
class ApartmentInstallmentAddToSapAPIView(APIView):
    def post(self, request, **kwargs):
        reservation = get_object_or_404(
            ApartmentReservation, pk=kwargs["apartment_reservation_id"]
        )
        installments = ApartmentInstallment.objects.filter(
            apartment_reservation_id=reservation.id
        ).order_by("id")

        if type_params := request.query_params.get("types"):
            types = [e for e in InstallmentType if e.value in type_params.split(",")]
            installments = installments.filter(type__in=types)

        if not installments.exists():
            raise Http404

        with transaction.atomic():
            for installment in installments:
                try:
                    installment.add_to_be_sent_to_sap()
                except AlreadyAddedToBeSentToSapError:
                    raise ValidationError(
                        f"{installment.type.value} already added to be sent to SAP."
                    )
                audit_logging.log(self.request.user, Operation.UPDATE, installment)

        seri = ApartmentInstallmentSerializer(
            reservation.apartment_installments.order_by("id"), many=True
        )
        return Response(seri.data)
