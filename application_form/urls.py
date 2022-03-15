from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.sales.views import (
    ApartmentReservationViewSet,
    execute_lottery_for_project,
    SalesApplicationViewSet,
)
from application_form.api.views import ApplicationViewSet, ListProjectReservations
from invoicing.api.views import (
    ApartmentInstallmentAPIView,
    ApartmentInstallmentInvoiceAPIView,
)

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet)
router.register(
    r"sales/applications", SalesApplicationViewSet, basename="sales-application"
)
router.register(
    r"sales/apartment_reservations",
    ApartmentReservationViewSet,
    basename="sales-apartment-reservation",
)


# URLs for public web pages
# URL-keyword 'me' means that the profile UUID will be retrieved from the authentication
# data.
public_urlpatterns = [
    path(
        r"profiles/me/projects/<uuid:project_uuid>/reservations",
        ListProjectReservations.as_view(),
        name="list_project_reservations",
    )
]

urlpatterns = [
    path(
        r"sales/execute_lottery_for_project",
        execute_lottery_for_project,
        name="execute_lottery_for_project",
    ),
    path(
        r"sales/apartment_reservations/<int:apartment_reservation_id>/installments/invoices/",  # noqa: E501
        ApartmentInstallmentInvoiceAPIView.as_view(),
        name="apartment-installment-invoice",
    ),
    path(
        r"sales/apartment_reservations/<int:apartment_reservation_id>/installments/",
        ApartmentInstallmentAPIView.as_view(),
        name="apartment-installment-list",
    ),
    path("", include(router.urls)),
]
urlpatterns += public_urlpatterns
