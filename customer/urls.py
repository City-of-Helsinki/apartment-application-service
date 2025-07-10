from django.urls import include, path
from rest_framework.routers import DefaultRouter

from customer.api.sales.views import CustomerCommentViewSet, CustomerViewSet

router = DefaultRouter()
router.register(
    r"sales/customers",
    CustomerViewSet,
    basename="sales-customer",
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "sales/customers/<int:customer_pk>/comments/",
        CustomerCommentViewSet.as_view({"get": "list", "post": "create"}),
        name="customer-comments",
    ),
]
