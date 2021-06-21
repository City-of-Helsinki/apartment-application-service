from django.urls import include, path
from rest_framework.routers import DefaultRouter

from application_form.api.views import ApplicationViewSet

router = DefaultRouter()
router.register(r"applications", ApplicationViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
