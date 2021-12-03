from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.views import ApplicationViewSet, SalesApplicationViewSet

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet)
router.register(
    r"sales/applications", SalesApplicationViewSet, basename="sales-application"
)

urlpatterns = [
    path("", include(router.urls)),
]
