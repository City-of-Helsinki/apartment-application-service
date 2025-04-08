from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apartment.api.views import (
    ApartmentAPIView,
    ApartmentReservationsAPIView,
    ProjectAPIView,
    ProjectExportApplicantsAPIView,
    ProjectExportApplicantsMailingListAPIView,
    ProjectExportLotteryResultsAPIView,
    ProjectExtraDataAPIView,
    SaleReportAPIView,
    SaleReportSelectedProjectsAPIView,
)
from invoicing.api.views import ProjectInstallmentTemplateAPIView

router = DefaultRouter()

urlpatterns = [
    path("sales/apartments/", ApartmentAPIView.as_view(), name="apartment-list"),
    path(
        "sales/apartments/<uuid:apartment_uuid>/reservations/",
        ApartmentReservationsAPIView.as_view(),
        name="apartment-detail-reservations-list",
    ),
    path("sales/report/", SaleReportAPIView.as_view(), name="sale-report"),
    path("sales/report/projects", SaleReportSelectedProjectsAPIView.as_view(), name="report-selected-project-list"),
    path(
        "sales/projects/",
        ProjectAPIView.as_view(),
        name="project-list",
    ),
    path(
        "sales/projects/<uuid:project_uuid>/",
        ProjectAPIView.as_view(),
        name="project-detail",
    ),
    path(
        "sales/projects/<uuid:project_uuid>/installment_templates/",
        ProjectInstallmentTemplateAPIView.as_view(),
        name="project-installment-template-list",
    ),
    path(
        "sales/projects/<uuid:project_uuid>/export_applicants/",
        ProjectExportApplicantsAPIView.as_view(),
        name="project-detail-export-applicant",
    ),
    path(
        "sales/projects/<uuid:project_uuid>/export_applicants_mailing_list/<str:export_type>",  # noqa: E501
        ProjectExportApplicantsMailingListAPIView.as_view(),
        name="project-detail-export-applicant-mailing-list",
    ),
    path(
        "sales/projects/<uuid:project_uuid>/export_lottery_result/",
        ProjectExportLotteryResultsAPIView.as_view(),
        name="project-detail-lottery-result",
    ),
    path(
        "sales/projects/<uuid:project_uuid>/extra_data/",
        ProjectExtraDataAPIView.as_view(),
        name="project-detail-extra-data",
    ),
    path("", include(router.urls)),
]
