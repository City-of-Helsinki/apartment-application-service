from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apartment.api.views import ProjectAPIView

router = DefaultRouter()

urlpatterns = [
    path("projects/", ProjectAPIView.as_view(), name="project-list"),
    path("", include(router.urls)),
]
