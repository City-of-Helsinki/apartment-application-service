from rest_framework.permissions import IsAuthenticated

from application_form.api.serializers import ApplicationSerializer
from application_form.models import Application
from audit_log.viewsets import AuditLoggingModelViewSet


class ApplicationViewSet(AuditLoggingModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "external_uuid"
    http_method_names = ["post"]
