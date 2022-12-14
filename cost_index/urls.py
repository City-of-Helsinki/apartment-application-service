from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cost_index.api.views import (
    apartment_revaluation_summary,
    ApartmentRevaluationViewSet,
    CostIndexViewSet,
)

router = DefaultRouter()

router.register(
    r"sales/cost_indexes",
    CostIndexViewSet,
    basename="sales-cost-index",
)

router.register(
    r"sales/apartment/revaluations",
    ApartmentRevaluationViewSet,
    basename="sales-apartment-revaluation",
)

urlpatterns = [
    path(
        r"sales/apartment/revaluations/summary",
        apartment_revaluation_summary,
        name="apartment-revaluation-summary",
    ),
    path("", include(router.urls)),
]
