from django.urls import include, path
from rest_framework.routers import DefaultRouter

from audit_log.api.views import AuditLogViewSet

router = DefaultRouter()
router.register(r"auditlogs", AuditLogViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
