from audit_log.viewsets import AuditLoggingModelViewSet
from cost_index.api.serializers import CostIndexSerializer
from cost_index.models import CostIndex


class CostIndexViewSet(AuditLoggingModelViewSet):
    queryset = CostIndex.objects.all()
    serializer_class = CostIndexSerializer
    http_method_names = ("get", "post", "put", "delete")
