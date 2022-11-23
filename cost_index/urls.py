from django.urls import include, path
from rest_framework.routers import DefaultRouter

from cost_index.api.views import CostIndexViewSet

router = DefaultRouter()

router.register(
    r"sales/cost_indexes",
    CostIndexViewSet,
    basename="sales-cost-index",
)

urlpatterns = [
    path("", include(router.urls)),
]
