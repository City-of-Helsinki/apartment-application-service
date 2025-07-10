from django.db.models import Q
from rest_framework import mixins, permissions, viewsets

from audit_log.viewsets import AuditLoggingModelViewSet
from customer.api.sales.serializers import (
    CustomerCommentSerializer,
    CustomerListSerializer,
    CustomerSerializer,
)
from customer.models import Customer, CustomerComment


class CustomerViewSet(AuditLoggingModelViewSet):
    SEARCH_VALUE_MIN_LENGTH = 2

    queryset = Customer.objects.all().order_by(
        "primary_profile__last_name", "primary_profile__first_name"
    )
    serializer_class = CustomerSerializer
    http_method_names = ["get", "post", "put", "head"]  # disable PATCH

    def get_queryset(self):
        if self.get_serializer_class() is CustomerListSerializer:
            first_name = self.request.query_params.get("first_name", "")
            last_name = self.request.query_params.get("last_name", "")
            phone_number = self.request.query_params.get("phone_number", "")
            email = self.request.query_params.get("email", "")
            search_values_less_than_min_length = all(
                len(value) < self.SEARCH_VALUE_MIN_LENGTH
                for value in [first_name, last_name, phone_number, email]
            )
            if search_values_less_than_min_length:
                return Customer.objects.none()

            queryset = Customer.objects.all().order_by(
                "primary_profile__last_name",
                "primary_profile__first_name",
                "secondary_profile__last_name",
                "secondary_profile__first_name",
            )
            if first_name:
                queryset = queryset.filter(
                    Q(primary_profile__first_name__icontains=first_name)
                    | Q(secondary_profile__first_name__icontains=first_name)
                )
            if last_name:
                queryset = queryset.filter(
                    Q(primary_profile__last_name__icontains=last_name)
                    | Q(secondary_profile__last_name__icontains=last_name)
                )
            if phone_number:
                queryset = queryset.filter(
                    Q(primary_profile__phone_number__icontains=phone_number)
                    | Q(secondary_profile__phone_number__icontains=phone_number)
                )
            if email:
                queryset = queryset.filter(
                    Q(primary_profile__email__icontains=email)
                    | Q(secondary_profile__email__icontains=email)
                )
            return queryset
        return super().get_queryset()

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        return super().get_serializer_class()


class CustomerCommentViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = CustomerCommentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        customer_id = self.kwargs["customer_pk"]
        return CustomerComment.objects.filter(customer_id=customer_id).select_related(
            "author", "customer"
        )

    def perform_create(self, serializer):
        customer = Customer.objects.get(pk=self.kwargs["customer_pk"])
        profile = self.request.user.profile
        serializer.save(customer=customer, author=profile)
