from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apartment.api.views import ApartmentAPIView, ProjectAPIView

router = DefaultRouter()

urlpatterns = [
    path("sales/apartments/", ApartmentAPIView.as_view(), name="apartment-list"),
    path("sales/projects/", ProjectAPIView.as_view(), name="project-list"),
    path("", include(router.urls)),
]
