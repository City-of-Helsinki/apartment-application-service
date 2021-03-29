from django.urls import include, path
from helusers.admin_site import admin
from rest_framework import routers

from application_form import urls as api_urls
from apartment_application_service.api.rpc_views import ApartmentApplicationRPC

router = routers.DefaultRouter()
router.register(r"apartment_application/?", ApartmentApplicationRPC, 'Apartment_application')

rpc_api_urls = router.urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", include((api_urls, 'application_form'), namespace="v1")),
    path("v1/", include((rpc_api_urls, 'apartment_application'))),
    path("", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
]
