from rest_framework import permissions

from audit_log.viewsets import AuditLoggingModelViewSet
from customer.api.sales.serializers import CustomerListSerializer, CustomerSerializer
from customer.models import Customer


class CustomerViewSet(AuditLoggingModelViewSet):
    queryset = Customer.objects.all().order_by(
        "primary_profile__last_name", "primary_profile__first_name"
    )
    serializer_class = CustomerSerializer
    permission_classes = [permissions.AllowAny]

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        return super().get_serializer_class()
