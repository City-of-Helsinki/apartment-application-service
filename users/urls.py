from django.urls import include, path
from rest_framework.routers import DefaultRouter

from users.api.views import ProfileViewSet

router = DefaultRouter()
router.register(r"profiles", ProfileViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
