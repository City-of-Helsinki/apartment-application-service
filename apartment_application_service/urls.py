from django.urls import include, path
from helusers.admin_site import admin

urlpatterns = [
    path("admin/", admin.site.urls),
    path("pysocial/", include("social_django.urls", namespace="social")),
    path("helauth/", include("helusers.urls")),
]
