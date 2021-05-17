from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from helusers.admin_site import admin

from application_form import urls as api_urls
from connections import urls as rpc_api_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", include((api_urls, "application_form"), namespace="v1/applications")),
    path("v1/", include((rpc_api_urls, "connections"), namespace="v1/connections")),
    path("", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
    path("openapi/", SpectacularAPIView.as_view(), name="schema"),
    path("api_docs/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path(
        "api_docs/swagger/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]
