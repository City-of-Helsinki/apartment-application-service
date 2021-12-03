from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated

from apartment.api.serializers import ProjectDocumentSerializer
from apartment.elastic.queries import get_projects


class ProjectAPIView(ListModelMixin, GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ProjectDocumentSerializer

    def get_queryset(self):
        return get_projects()

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)
