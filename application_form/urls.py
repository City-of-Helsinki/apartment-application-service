from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.sales.views import (
    apartment_states,
    ApartmentReservationViewSet,
    execute_lottery_for_project,
    mark_offer_reminder_sent,
    OfferViewSet,
    pending_offer_reminders,
    SalesApplicationViewSet,
)
from application_form.api.views import (
    ApplicationViewSet,
    CustomerOfferDetailsView,
    CustomerOfferMessageView,
    CustomerOfferUpdateView,
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
    ),
    path(
        r"profiles/me/offers/<int:offer_id>/",
        CustomerOfferUpdateView.as_view(),
        name="customer_offer_update",
    ),
    path(
        r"profiles/me/offers/<int:offer_id>/offer_message/",
        CustomerOfferMessageView.as_view(),
        name="customer_offer_message",
    ),
    path(
        r"profiles/me/offers/<int:offer_id>/details/",
        CustomerOfferDetailsView.as_view(),
        name="customer_offer_details",
    ),
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
        r"sales/offers/pending_reminders/",
        pending_offer_reminders,
        name="pending_offer_reminders",
    ),
    path(
        r"sales/offers/<int:offer_id>/mark_reminder_sent/",
        mark_offer_reminder_sent,
        name="mark_offer_reminder_sent",
    ),
    path(
        r"sales/applicant/latest/<int:customer_id>/",
        LatestApplicantInfo.as_view(),
        name="applicant-by-customer",
    ),
    path("", include(router.urls)),
]
urlpatterns += public_urlpatterns
