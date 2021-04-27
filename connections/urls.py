from django.urls import include, path
from rest_framework import routers

from connections.api.views import Connections

app_name = "connections"


router = routers.DefaultRouter()
router.register(r"connections/?", Connections, "Connections")

urlpatterns = [
    path("", include(router.urls)),
]
