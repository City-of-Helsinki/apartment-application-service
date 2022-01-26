from django.core.exceptions import ObjectDoesNotExist
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apartment.api.serializers import (
    ApartmentDocumentSerializer,
    ProjectDocumentDetailSerializer,
    ProjectDocumentListSerializer,
)
from apartment.elastic.queries import get_apartments, get_projects


class ApartmentAPIView(APIView):
    permission_classes = [
        permissions.AllowAny,
    ]
    http_method_names = ["get"]

    def get(self, request):
        project_uuid = request.GET.get("project_uuid", None)
        apartments = get_apartments(project_uuid)
        serializer = ApartmentDocumentSerializer(apartments, many=True)
        return Response(serializer.data)


class ProjectAPIView(APIView):
    permission_classes = [
        permissions.AllowAny,
    ]
    http_method_names = ["get"]

    def get(self, request, project_uuid=None):
        many = project_uuid is None
        try:
            project_data = get_projects(project_uuid)
            if not many:
                project_data = project_data[0]
        except ObjectDoesNotExist:
            raise NotFound()
        serializer_class = (
            ProjectDocumentListSerializer if many else ProjectDocumentDetailSerializer
        )
        serializer = serializer_class(project_data, many=many)
        return Response(serializer.data)
