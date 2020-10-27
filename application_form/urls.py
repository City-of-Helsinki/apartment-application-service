from django.urls import include, path
from rest_framework import routers

from application_form.api import views

app_name = "application_form"

router = routers.DefaultRouter()
router.register(r"haso_application", views.HasoApplicationViewSet)
router.register(r"hitas_application", views.HitasApplicationViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
