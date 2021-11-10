from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from helusers.admin_site import admin

from application_form import urls as applications_urls
from audit_log import urls as auditlogs_api_urls
from connections import urls as connections_api_urls
from users import urls as users_urls
from users.api.views import MaskedTokenObtainPairView, MaskedTokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "v1/",
        include((auditlogs_api_urls, "audit_log"), namespace="v1/auditlogs"),
    ),
    path(
        "v1/",
        include((connections_api_urls, "connections"), namespace="v1/connections"),
    ),
    path(
        "v1/",
        include((applications_urls, "application_form"), namespace="v1/applications"),
    ),
    path("v1/", include((users_urls, "users"), namespace="v1/profiles")),
    path("v1/token/", MaskedTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("v1/token/refresh/", MaskedTokenRefreshView.as_view(), name="token_refresh"),
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
