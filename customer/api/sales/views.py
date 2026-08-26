from datetime import datetime

from django.db.models import Case, F, IntegerField, Prefetch, Q, Value, When
from django.shortcuts import get_object_or_404
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apartment.elastic.queries import get_apartments_for_uuids
from application_form.enums import ApartmentReservationState
from application_form.models import (
    ApartmentReservation,
    ApartmentReservationStateChangeEvent,
    LotteryEvent,
)
from audit_log.viewsets import AuditLoggingModelViewSet
from customer.api.sales.serializers import (
    CustomerApartmentReservationSerializer,
    CustomerCommentSerializer,
    CustomerListSerializer,
    CustomerSerializer,
)
from customer.models import Customer, CustomerComment
from invoicing.models import ApartmentInstallment

_ALONE_PARTNER_SENTINEL = "<ALONE>"


def _normalize_hetu(value):
    """Return a normalized hetu-like string with surrounding whitespace removed."""
    return (value or "").strip()


def _has_meaningful_value(value) -> bool:
    """Return whether value should overwrite merged list attributes."""
    if value is None:
        return False
    if isinstance(value, str):
        normalized_value = value.strip()
        return bool(normalized_value and normalized_value != "-")
    return True


def _merge_customer_list_row_from_latest(
    *,
    canonical_customer: Customer,
    latest_customer: Customer,
) -> Customer:
    """Merge list-visible attributes from latest customer into canonical customer."""
    if canonical_customer.id == latest_customer.id:
        return canonical_customer

    primary_profile_fields = [
        "first_name",
        "last_name",
        "email",
        "phone_number",
    ]
    for field_name in primary_profile_fields:
        latest_value = getattr(latest_customer.primary_profile, field_name)
        if _has_meaningful_value(latest_value):
            setattr(canonical_customer.primary_profile, field_name, latest_value)

    if canonical_customer.secondary_profile and latest_customer.secondary_profile:
        secondary_profile_fields = ["first_name", "last_name"]
        for field_name in secondary_profile_fields:
            latest_value = getattr(latest_customer.secondary_profile, field_name)
            if _has_meaningful_value(latest_value):
                setattr(canonical_customer.secondary_profile, field_name, latest_value)

    if _has_meaningful_value(latest_customer.right_of_residence):
        canonical_customer.right_of_residence = latest_customer.right_of_residence

    return canonical_customer


def _get_participant_partners(*, hetu: str, cache: dict | None = None) -> set[str]:
    """Return distinct partner hetu values for a person across all customers."""
    participant_partners_cache = (
        cache.setdefault("participant_partners_cache", {}) if cache is not None else {}
    )
    if hetu in participant_partners_cache:
        return participant_partners_cache[hetu]

    candidates = Customer.objects.select_related(
        "primary_profile", "secondary_profile"
    ).filter(
        Q(primary_profile__national_identification_number=hetu)
        | Q(secondary_profile__national_identification_number=hetu)
    )

    partners = set()
    for candidate in candidates:
        candidate_primary_hetu = _normalize_hetu(
            getattr(candidate.primary_profile, "national_identification_number", None)
        )
        candidate_secondary_hetu = _normalize_hetu(
            getattr(candidate.secondary_profile, "national_identification_number", None)
        )
        if candidate_primary_hetu == hetu:
            partners.add(candidate_secondary_hetu or _ALONE_PARTNER_SENTINEL)
        if candidate_secondary_hetu == hetu:
            partners.add(candidate_primary_hetu or _ALONE_PARTNER_SENTINEL)

    participant_partners_cache[hetu] = partners
    return partners


def _get_customer_hetu_candidates(customer: Customer) -> list[str]:
    """Return normalized primary and secondary hetu candidates for customer."""
    return [
        _normalize_hetu(
            getattr(customer.primary_profile, "national_identification_number", None)
        ),
        _normalize_hetu(
            getattr(customer.secondary_profile, "national_identification_number", None)
        ),
    ]


def _get_hetu_customer_candidates(
    hetu: str,
    *,
    cache: dict | None = None,
) -> list[Customer]:
    """Return customers where the given hetu appears in primary or secondary."""
    hetu_candidates_cache = (
        cache.setdefault("hetu_candidates_cache", {}) if cache is not None else {}
    )
    if hetu in hetu_candidates_cache:
        return hetu_candidates_cache[hetu]

    candidates = list(
        Customer.objects.select_related("primary_profile", "secondary_profile")
        .filter(
            Q(primary_profile__national_identification_number=hetu)
            | Q(secondary_profile__national_identification_number=hetu)
        )
        .order_by("id")
    )

    hetu_candidates_cache[hetu] = candidates
    return candidates


def _build_hetu_participation(
    *,
    candidates: list[Customer],
    hetu: str,
) -> tuple[set, set]:
    """Return participant customer IDs and partner hetu set for one hetu."""
    participant_customer_ids = set()
    participant_partners = set()

    for candidate in candidates:
        candidate_primary_hetu = _normalize_hetu(
            getattr(candidate.primary_profile, "national_identification_number", None)
        )
        candidate_secondary_hetu = _normalize_hetu(
            getattr(candidate.secondary_profile, "national_identification_number", None)
        )

        if candidate_primary_hetu == hetu:
            participant_customer_ids.add(candidate.id)
            participant_partners.add(
                candidate_secondary_hetu or _ALONE_PARTNER_SENTINEL
            )
        if candidate_secondary_hetu == hetu:
            participant_customer_ids.add(candidate.id)
            participant_partners.add(candidate_primary_hetu or _ALONE_PARTNER_SENTINEL)

    return participant_customer_ids, participant_partners


def _resolve_safe_solo_customer_group_ids(
    customer: Customer,
    *,
    cache: dict | None = None,
) -> list[int] | None:
    """Return safe-solo group IDs, or None when customer is not safe-solo."""
    hetu_candidates = _get_customer_hetu_candidates(customer)

    hetu_candidates = [hetu for hetu in hetu_candidates if hetu]
    safe_solo_cache = cache.setdefault("safe_solo_cache", {}) if cache else {}

    for hetu in hetu_candidates:
        if hetu in safe_solo_cache:
            cached_group = safe_solo_cache[hetu]
            if cached_group and customer.id in cached_group:
                return cached_group
            continue

        candidates = _get_hetu_customer_candidates(hetu, cache=cache)

        if len(candidates) <= 1:
            safe_solo_cache[hetu] = None
            continue

        participant_customer_ids, participant_partners = _build_hetu_participation(
            candidates=candidates,
            hetu=hetu,
        )

        if (
            len(participant_customer_ids) > 1
            and participant_partners == {_ALONE_PARTNER_SENTINEL}
            and customer.id in participant_customer_ids
        ):
            grouped_ids = sorted(participant_customer_ids)
            safe_solo_cache[hetu] = grouped_ids
            return grouped_ids

        safe_solo_cache[hetu] = None

    return None


def _resolve_strict_safe_pair_customer_group_ids(
    customer: Customer,
    *,
    cache: dict | None = None,
) -> list[int] | None:
    """Return strict safe-pair group IDs, or None when not eligible."""
    primary_hetu, secondary_hetu = _get_customer_hetu_candidates(customer)

    if not (primary_hetu and secondary_hetu):
        return None

    pair_key = tuple(sorted([primary_hetu, secondary_hetu]))
    safe_pair_cache = cache.setdefault("safe_pair_cache", {}) if cache else {}
    if pair_key in safe_pair_cache:
        cached_group = safe_pair_cache[pair_key]
        if cached_group and customer.id in cached_group:
            return cached_group
        return None

    pair_customer_ids = []
    pair_candidates = list(
        Customer.objects.select_related("primary_profile", "secondary_profile")
        .filter(
            Q(
                primary_profile__national_identification_number=primary_hetu,
                secondary_profile__national_identification_number=secondary_hetu,
            )
            | Q(
                primary_profile__national_identification_number=secondary_hetu,
                secondary_profile__national_identification_number=primary_hetu,
            )
        )
        .order_by("id")
    )

    for candidate in pair_candidates:
        candidate_primary_hetu, candidate_secondary_hetu = (
            _get_customer_hetu_candidates(candidate)
        )
        if {candidate_primary_hetu, candidate_secondary_hetu} == {
            primary_hetu,
            secondary_hetu,
        }:
            pair_customer_ids.append(candidate.id)

    if len(pair_customer_ids) <= 1 or customer.id not in pair_customer_ids:
        safe_pair_cache[pair_key] = None
        return None

    primary_partners = _get_participant_partners(hetu=primary_hetu, cache=cache)
    secondary_partners = _get_participant_partners(hetu=secondary_hetu, cache=cache)
    if primary_partners == {secondary_hetu} and secondary_partners == {primary_hetu}:
        grouped_ids = sorted(pair_customer_ids)
        safe_pair_cache[pair_key] = grouped_ids
        return grouped_ids

    safe_pair_cache[pair_key] = None
    return None


def _resolve_customer_group_customer_ids(
    customer: Customer,
    *,
    cache: dict | None = None,
) -> list[int]:
    """Return grouping IDs for strict safe-solo and strict safe-pair rules."""
    customer_group_cache = (
        cache.setdefault("customer_group_cache", {}) if cache is not None else {}
    )
    if customer.id in customer_group_cache:
        return customer_group_cache[customer.id]

    safe_solo_group = _resolve_safe_solo_customer_group_ids(customer, cache=cache)
    if safe_solo_group is not None:
        for grouped_customer_id in safe_solo_group:
            customer_group_cache[grouped_customer_id] = safe_solo_group
        return safe_solo_group

    safe_pair_group = _resolve_strict_safe_pair_customer_group_ids(
        customer,
        cache=cache,
    )
    if safe_pair_group is not None:
        for grouped_customer_id in safe_pair_group:
            customer_group_cache[grouped_customer_id] = safe_pair_group
        return safe_pair_group

    customer_group_cache[customer.id] = [customer.id]
    return [customer.id]


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
            hetu = self.request.query_params.get("hetu", "")
            date_of_birth_raw = self.request.query_params.get("date_of_birth", "")
            search_values_less_than_min_length = all(
                len(value) < self.SEARCH_VALUE_MIN_LENGTH
                for value in [
                    first_name,
                    last_name,
                    phone_number,
                    email,
                    hetu,
                    date_of_birth_raw,
                ]
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
            if hetu:
                queryset = queryset.filter(
                    Q(primary_profile__national_identification_number=hetu)
                    | Q(secondary_profile__national_identification_number=hetu)
                )
            if date_of_birth_raw:
                date_of_birth = self._parse_finnish_date(date_of_birth_raw)
                if date_of_birth is None:
                    return Customer.objects.none()
                queryset = queryset.filter(
                    Q(primary_profile__date_of_birth=date_of_birth)
                    | Q(secondary_profile__date_of_birth=date_of_birth)
                )
            return queryset
        return super().get_queryset()

    @staticmethod
    def _parse_finnish_date(value):
        """
        Parse a date string in Finnish format (d.m.Y) into a date object.

                Parameters:
                        value (str): A date string in format d.m.Y, e.g. "3.9.1978"

                Returns:
                        date | None: Parsed date, or None if the format is invalid
        """
        try:
            return datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            return None

    def get_serializer_class(self):
        if self.action == "list":
            return CustomerListSerializer
        if self.action == "apartment_reservations":
            return CustomerApartmentReservationSerializer
        return super().get_serializer_class()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        if self.get_serializer_class() is not CustomerListSerializer:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        customers = list(
            queryset.select_related("primary_profile", "secondary_profile")
        )
        by_id = {customer.id: customer for customer in customers}
        grouping_cache = {}

        deduplicated_customers = []
        seen_canonical_ids = set()
        for customer in customers:
            grouped_ids = _resolve_customer_group_customer_ids(
                customer,
                cache=grouping_cache,
            )
            canonical_id = min(grouped_ids)
            if canonical_id in seen_canonical_ids:
                continue

            group_customers = [
                by_id[customer_id]
                for customer_id in sorted(grouped_ids)
                if customer_id in by_id
            ]
            if not group_customers:
                continue

            canonical_customer = group_customers[0]
            latest_customer = group_customers[-1]
            seen_canonical_ids.add(canonical_id)
            deduplicated_customers.append(
                _merge_customer_list_row_from_latest(
                    canonical_customer=canonical_customer,
                    latest_customer=latest_customer,
                )
            )

        serializer = self.get_serializer(deduplicated_customers, many=True)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="apartment_reservations",
        pagination_class=CustomerReservationsPagination,
    )
    def apartment_reservations(self, request, pk=None):
        """
        Return the customer's apartment reservations as a paginated list.

        Apartment metadata is loaded from the Drupal Search API in parallel for
        the distinct apartment UUIDs on the current page (with short-lived
        per-UUID caching). Pagination keeps work bounded regardless of how many
        reservations the customer has overall.

        Ordering (DB-side, stable across pages):
          1. non-canceled reservations first
          2. queue_position ascending, nulls last
          3. id ascending
        """
        customer = self.get_object()
        grouped_customer_ids = _resolve_customer_group_customer_ids(customer)
        queryset = (
            ApartmentReservation.objects.filter(customer_id__in=grouped_customer_ids)
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
            .related_fields()
            .prefetch_related(
                Prefetch(
                    "state_change_events",
                    queryset=ApartmentReservationStateChangeEvent.objects.order_by(
                        "id"
                    ).select_related("user", "user__profile"),
                ),
                Prefetch(
                    "apartment_installments",
                    queryset=ApartmentInstallment.objects.order_by(
                        "id"
                    ).prefetch_related("payments"),
                ),
            )
        )

        paginator = CustomerReservationsPagination()
        page = paginator.paginate_queryset(queryset, request, view=self)
        page_list = list(page) if page is not None else []
        apartment_uuids = [r.apartment_uuid for r in page_list]
        apartment_map = get_apartments_for_uuids(
            apartment_uuids, include_project_fields=True
        )
        distinct_uuids = {str(u) for u in apartment_uuids}
        lottery_completed_apartment_uuids = set(
            LotteryEvent.objects.filter(apartment_uuid__in=distinct_uuids).values_list(
                "apartment_uuid", flat=True
            )
        )
        lottery_completed_apartment_uuids = {
            str(u) for u in lottery_completed_apartment_uuids
        }
        serializer = CustomerApartmentReservationSerializer(
            page_list,
            many=True,
            context={
                **self.get_serializer_context(),
                "apartment_map": apartment_map,
                "lottery_completed_apartment_uuids": lottery_completed_apartment_uuids,
            },
        )
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
        customer = get_object_or_404(Customer, pk=customer_id)
        grouped_customer_ids = _resolve_customer_group_customer_ids(customer)
        return CustomerComment.objects.filter(
            customer_id__in=grouped_customer_ids
        ).select_related("author_user", "customer")

    def perform_create(self, serializer):
        customer = get_object_or_404(Customer, pk=self.kwargs["customer_pk"])
        grouped_customer_ids = _resolve_customer_group_customer_ids(customer)
        canonical_customer = Customer.objects.get(pk=min(grouped_customer_ids))
        user = self.request.user
        serializer.save(customer=canonical_customer, author_user=user)
