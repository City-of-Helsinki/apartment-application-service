from django.db.models import Case, F, IntegerField, Q, Value, When
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination

from application_form.enums import ApartmentReservationState
from application_form.models import ApartmentReservation
from audit_log.viewsets import AuditLoggingModelViewSet
from customer.api.sales.serializers import (
    CustomerApartmentReservationSerializer,
    CustomerCommentSerializer,
    CustomerListSerializer,
    CustomerSerializer,
)
from customer.models import Customer, CustomerComment


class CustomerReservationsPagination(PageNumberPagination):
    """Pagination for the customer's apartment reservations sub-resource."""

    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 50


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
        if self.action == "apartment_reservations":
            return CustomerApartmentReservationSerializer
        return super().get_serializer_class()

    @action(
        detail=True,
        methods=["get"],
        url_path="apartment_reservations",
        pagination_class=CustomerReservationsPagination,
    )
    def apartment_reservations(self, request, pk=None):
        """
        Return the customer's apartment reservations as a paginated list.

        Each serialized row performs a Drupal Search API lookup for the
        apartment, so pagination keeps the response time bounded regardless
        of how many reservations the customer has.

        Ordering (DB-side, stable across pages):
          1. non-canceled reservations first
          2. queue_position ascending, nulls last
          3. id ascending
        """
        customer = self.get_object()
        queryset = (
            ApartmentReservation.objects.filter(customer=customer)
            .annotate(
                _is_canceled=Case(
                    When(
                        state=ApartmentReservationState.CANCELED.value,
                        then=Value(1),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by(
                "_is_canceled",
                F("queue_position").asc(nulls_last=True),
                "id",
            )
        )

        paginator = CustomerReservationsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = CustomerApartmentReservationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


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
            "author_user", "customer"
        )

    def perform_create(self, serializer):
        customer = Customer.objects.get(pk=self.kwargs["customer_pk"])
        user = self.request.user
        serializer.save(customer=customer, author_user=user)
