from rest_framework.permissions import IsAuthenticated

from application_form.api.serializers import (
    ApplicationSerializer,
    SalesApplicationSerializer,
)
from application_form.models import Application
from audit_log.viewsets import AuditLoggingModelViewSet
from users.permissions import IsSalesperson


class ApplicationViewSet(AuditLoggingModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "external_uuid"
    http_method_names = ["post"]


class SalesApplicationViewSet(ApplicationViewSet):
    serializer_class = SalesApplicationSerializer
    permission_classes = [IsAuthenticated, IsSalesperson]
