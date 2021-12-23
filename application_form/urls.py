from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.sales.views import (
    execute_lottery_for_project,
    SalesApplicationViewSet,
)
from application_form.api.views import ApplicationViewSet

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet)
router.register(
    r"sales/applications", SalesApplicationViewSet, basename="sales-application"
)

urlpatterns = [
    path(
        r"sales/execute_lottery_for_project",
        execute_lottery_for_project,
        name="execute_lottery_for_project",
    ),
    path("", include(router.urls)),
]
