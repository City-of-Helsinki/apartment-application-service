from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from audit_log.api.serializers import AuditLogSerializer
from audit_log.models import AuditLog


class AuditLogViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated]
