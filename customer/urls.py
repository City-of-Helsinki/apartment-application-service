from django.urls import include, path
from rest_framework.routers import DefaultRouter

from customer.api.sales.views import CustomerViewSet

router = DefaultRouter()
router.register(
    r"sales/customers",
    CustomerViewSet,
    basename="sales-customer",
)

urlpatterns = [
    path("", include(router.urls)),
]
