from django.db import transaction
from django.http import HttpResponse
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.views import APIView

from application_form.models import ApartmentReservation

from ..api.serializers import (
    ApartmentInstallmentSerializer,
    ProjectInstallmentTemplateSerializer,
)
from ..models import ApartmentInstallment, ProjectInstallmentTemplate
from ..pdf import create_invoice_pdf_from_installments

INVOICE_FILE_NAME = "invoice.pdf"


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
        # we want to always create new objects instead of updating possible already
        # existing ones, so the old ones are deleted first
        self.get_queryset().delete()
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


class ApartmentInstallmentInvoiceAPIView(APIView):
    def get(self, request, **kwargs):
        reservation = ApartmentReservation.objects.get(
            id=kwargs["apartment_reservation_id"]
        )
        installments = list(reservation.apartment_installments.all().order_by("id"))
        pdf_data = create_invoice_pdf_from_installments(installments)
        response = HttpResponse(pdf_data, content_type="application/pdf")
        response["Content-Disposition"] = f"attachment; filename={INVOICE_FILE_NAME}"

        return response
