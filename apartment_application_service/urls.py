from django.urls import include, path
from helusers.admin_site import admin
from rest_framework import routers

from application_form import urls as api_urls

router = routers.DefaultRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", include(api_urls, namespace="v1")),
    path("", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
]
