from django.urls import include, path
from rest_framework.routers import DefaultRouter

from users.api.views import ProfileViewSet, SalesPersonViewSet

router = DefaultRouter()
router.register(r"profiles", ProfileViewSet)
router.register(r"sales/salespersons", SalesPersonViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
