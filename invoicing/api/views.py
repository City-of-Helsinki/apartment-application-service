from django.db import transaction
from django.utils.timezone import now
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics

from ..api.serializers import ProjectInstallmentTemplateSerializer
from ..models import ProjectInstallmentTemplate


@extend_schema_view(
    post=extend_schema(
        description="Recreates a project's all installment templates in a single "
        "request."
    )
)
class ProjectInstallmentTemplateAPIView(generics.ListCreateAPIView):
    queryset = ProjectInstallmentTemplate.objects.all()
    serializer_class = ProjectInstallmentTemplateSerializer

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(project_uuid=self.kwargs["project_uuid"])
            .order_by("id")
        )

    def get_serializer(self, *args, **kwargs):
        # this is required to be able to create a list of objects
        kwargs["many"] = True
        return super().get_serializer(*args, **kwargs)

    @transaction.atomic
    def perform_create(self, serializer):
        # we want to always create new ProjectInstallmentTemplate objects for the
        # Project instead of updating possible already existing ones, so the old ones
        # are deleted first
        self.get_queryset().delete()
        # created_at is set here to get exactly the same timestamp on all instances
        serializer.save(project_uuid=self.kwargs["project_uuid"], created_at=now())
