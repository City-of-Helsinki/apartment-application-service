from django.urls import include, path
from helusers.admin_site import admin

from application_form import urls as form_api_urls
from connections import urls as connections_api_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "v1/", include((form_api_urls, "application_form"), namespace="v1/applications")
    ),
    path(
        "v1/",
        include((connections_api_urls, "connections"), namespace="v1/connections"),
    ),
    path("", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
]
