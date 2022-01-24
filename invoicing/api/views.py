from django.db import transaction
from django.utils.timezone import now
from rest_framework import generics

from ..api.serializers import ProjectInstallmentTemplateSerializer
from ..models import ProjectInstallmentTemplate


class ProjectInstallmentAPIView(generics.ListCreateAPIView):
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
        self.get_queryset().delete()
        # created_at is set here to get exactly the same timestamp on all instances
        serializer.save(project_uuid=self.kwargs["project_uuid"], created_at=now())
