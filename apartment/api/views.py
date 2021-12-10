from rest_framework import permissions
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apartment.api.serializers import (
    ApartmentDocumentSerializer,
    ProjectDocumentSerializer,
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
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = get_projects()
        serializer = ProjectDocumentSerializer(projects, many=True)
        return Response(serializer.data)
