from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils.timezone import now
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from apartment.elastic.queries import get_apartment
from application_form.models import ApartmentReservation

from ..api.serializers import (
    ApartmentInstallmentSerializer,
    ProjectInstallmentTemplateSerializer,
)
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

    @transaction.atomic
    def perform_create(self, serializer):
        queryset = self.get_queryset()

        # make old instances available in the serializer so that values from those can
        # be used when creating new instances if needed
        old_instances = {instance.type: instance for instance in queryset}
        serializer.context.update({"old_instances": old_instances})

        # we want to always create new instances instead of updating possible already
        # existing ones, so the old ones are deleted first
        queryset.delete()

        # created_at is set here to get exactly the same timestamp on all instances
        serializer.save(
            **{self.parent_field: self.kwargs[self.parent_field], "created_at": now()}
        )


@extend_schema_view(
    post=extend_schema(
        description="Recreates a project's all installment templates in a single "
        "request."
    )
)
class ProjectInstallmentTemplateAPIView(InstallmentAPIViewBase):
    queryset = ProjectInstallmentTemplate.objects.all()
    serializer_class = ProjectInstallmentTemplateSerializer
    parent_field = "project_uuid"


@extend_schema_view(
    post=extend_schema(
        description="Recreates an apartment reservation's all installments in a single "
        "request."
    )
)
class ApartmentInstallmentAPIView(InstallmentAPIViewBase):
    queryset = ApartmentInstallment.objects.all()
    serializer_class = ApartmentInstallmentSerializer
    parent_field = "apartment_reservation_id"


@extend_schema(
    description="Create an invoice PDF based on apartment installments.",
    parameters=[
        OpenApiParameter(
            name="index",
            description="Comma-separated row index numbers starting from 0.",
            type={"type": "array", "items": {"type": "number"}},
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
        installments = list(
            ApartmentInstallment.objects.filter(
                apartment_reservation_id=reservation.id
            ).order_by("id")
        )
        if not installments:
            raise Http404

        if index_params := request.query_params.get("index"):
            installments = [
                _find_installment_by_index_param(index_param, installments)
                for index_param in index_params.split(",")
            ]

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
            name="index",
            description="Comma-separated row index numbers starting from 0.",
            type={"type": "array", "items": {"type": "number"}},
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
        installments = list(
            ApartmentInstallment.objects.filter(
                apartment_reservation_id=reservation.id
            ).order_by("id")
        )
        if not installments:
            raise Http404

        if index_params := request.query_params.get("index"):
            installments = [
                _find_installment_by_index_param(index_param, installments)
                for index_param in index_params.split(",")
            ]

        with transaction.atomic():
            for installment in installments:
                try:
                    installment.add_to_be_sent_to_sap()
                except AlreadyAddedToBeSentToSapError:
                    raise ValidationError(
                        f"{installment.type.value} already added to be sent to SAP."
                    )

        seri = ApartmentInstallmentSerializer(
            reservation.apartment_installments.order_by("id"), many=True
        )
        return Response(seri.data)


def _find_installment_by_index_param(index_param, installments):
    try:
        return next(
            installment
            for index, installment in enumerate(installments)
            if str(index) == index_param.strip()
        )
    except StopIteration:
        raise ValidationError(f"Invalid index {index_param}")
