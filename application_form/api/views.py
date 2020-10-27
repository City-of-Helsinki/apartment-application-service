from rest_framework import viewsets

from application_form.api.serializers import HasoSerializer, HitasSerializer
from application_form.models import HasoApplication, HitasApplication


class HasoApplicationViewSet(viewsets.ModelViewSet):
    queryset = HasoApplication.objects.all()
    serializer_class = HasoSerializer


class HitasApplicationViewSet(viewsets.ModelViewSet):
    queryset = HitasApplication.objects.all()
    serializer_class = HitasSerializer
