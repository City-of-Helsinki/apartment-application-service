from rest_framework.viewsets import ModelViewSet

from users.api.serializers import ProfileSerializer
from users.models import Profile


class ProfileViewSet(ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
