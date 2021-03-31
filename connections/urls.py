from django.urls import include, path
from rest_framework import routers
from connections.api.rpc_views import ConnectionsRPC


app_name = "connections"


router = routers.DefaultRouter()
router.register(r"connections/?", ConnectionsRPC, "Connections")

urlpatterns = [
    path("", include(router.urls)),
]
