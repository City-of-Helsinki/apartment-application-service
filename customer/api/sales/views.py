from rest_framework import permissions

from audit_log.viewsets import AuditLoggingModelViewSet
from customer.api.sales.serializers import CustomerListSerializer
from customer.models import Customer


class CustomerViewSet(AuditLoggingModelViewSet):
    queryset = Customer.objects.all().order_by(
        "primary_profile__last_name", "primary_profile__first_name"
    )
    serializer_class = CustomerListSerializer
    permission_classes = [permissions.AllowAny]
