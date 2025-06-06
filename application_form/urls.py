from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.sales.views import (
    apartment_states,
    ApartmentReservationViewSet,
    execute_lottery_for_project,
    OfferViewSet,
    SalesApplicationViewSet,
)
from application_form.api.views import (
    ApplicationViewSet,
    DeleteApplicationView,
    LatestApplicantInfo,
    ListProjectReservations,
)
from invoicing.api.views import (
    ApartmentInstallmentAddToSapAPIView,
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
router.register(
    r"sales/offers",
    OfferViewSet,
    basename="sales-offer",
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
        r"applications/delete/<uuid:application_uuid>/",
        DeleteApplicationView.as_view(),
        name="application-delete",
    ),
    path(
        r"sales/execute_lottery_for_project/",
        execute_lottery_for_project,
        name="execute_lottery_for_project",
    ),
    path(
        r"sales/apartment_reservations/<int:apartment_reservation_id>/installments/invoices/",  # noqa: E501
        ApartmentInstallmentInvoiceAPIView.as_view(),
        name="apartment-installment-invoice",
    ),
    path(
        r"sales/apartment_reservations/<int:apartment_reservation_id>/installments/add_to_be_sent_to_sap/",  # noqa: E501
        # noqa: E501
        ApartmentInstallmentAddToSapAPIView.as_view(),
        name="apartment-installment-add-to-be-sent-to-sap",
    ),
    path(
        r"sales/apartment_reservations/<int:apartment_reservation_id>/installments/",
        ApartmentInstallmentAPIView.as_view(),
        name="apartment-installment-list",
    ),
    path(
        r"sales/apartment_states/",
        apartment_states,
        name="apartment_states",
    ),
    path(
        r"sales/applicant/latest/<int:customer_id>/",
        LatestApplicantInfo.as_view(),
        name="applicant-by-customer",
    ),
    path("", include(router.urls)),
]
urlpatterns += public_urlpatterns
