from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.sales.views import (
    execute_lottery_for_project,
    SalesApplicationViewSet,
)
from application_form.api.views import ApplicationViewSet, ListProjectReservations

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet)
router.register(
    r"sales/applications", SalesApplicationViewSet, basename="sales-application"
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
    path("", include(router.urls)),
]
urlpatterns += public_urlpatterns
