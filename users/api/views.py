from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from audit_log.viewsets import AuditLoggingModelViewSet
from users.api.permissions import IsCreatingOrAuthenticated
from users.api.serializers import (
    MaskedTokenObtainPairSerializer,
    ProfileSerializer,
    UserSerializer,
)
from users.enums import Roles
from users.masking import mask_string, mask_uuid, unmask_uuid
from users.models import Profile

MASKED_ID_PARAMETER = OpenApiParameter(
    name="id",
    type={"type": "string"},
    location=OpenApiParameter.PATH,
    required=True,
    description="A masked UUID string identifying this profile.",
)


class SalesPersonViewSet(AuditLoggingModelViewSet):
    queryset = (
        get_user_model()
        .objects.filter(groups__name__iexact=Roles.DJANGO_SALESPERSON.name)
        .exclude(first_name="")
    )
    serializer_class = UserSerializer
    http_method_names = ["get"]


@extend_schema_view(
    create=extend_schema(responses=ProfileSerializer.CreateResponseSerializer, auth=[]),
    list=extend_schema(exclude=True),
    retrieve=extend_schema(parameters=[MASKED_ID_PARAMETER]),
    update=extend_schema(parameters=[MASKED_ID_PARAMETER]),
    destroy=extend_schema(parameters=[MASKED_ID_PARAMETER]),
)
class ProfileViewSet(AuditLoggingModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsCreatingOrAuthenticated]
    http_method_names = ["get", "post", "put", "delete"]

    def initial(self, request, *args, **kwargs):
        if self.lookup_field in self.kwargs:
            self.kwargs[self.lookup_field] = unmask_uuid(self.kwargs[self.lookup_field])
        super().initial(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        credentials = self._create_credentials(serializer.instance.user)
        return Response(credentials, status=status.HTTP_201_CREATED)

    def _create_credentials(self, user) -> dict:
        password = get_user_model().objects.make_random_password(length=32)
        user.set_password(password)
        user.save(update_fields=["password"])
        return {
            MaskedTokenObtainPairSerializer.profile_id_field: mask_uuid(
                user.profile.pk
            ),
            MaskedTokenObtainPairSerializer.password_field: mask_string(password),
        }


@extend_schema_view(
    post=extend_schema(
        summary="Create token pair",
        responses={200: MaskedTokenObtainPairSerializer.ResponseSerializer},
    ),
)
class MaskedTokenObtainPairView(TokenObtainPairView):
    """
    Takes a set of masked user credentials and returns an access and refresh
    JSON web token pair to prove the authentication of those credentials.

    The access token is a short-lived token which can be used to gain access to
    other endpoints until it expires.

    The refresh token is a longer-lived token which can be used to request for
    a new access token without having to do a "full" login with profile ID and
    password. When the refresh token expires, a full login is required.
    """

    # def post(self, request):
    #     import ipdb;ipdb.set_trace()
    #     pass

    serializer_class = MaskedTokenObtainPairSerializer


@extend_schema_view(post=extend_schema(summary="Refresh access token"))
class MaskedTokenRefreshView(TokenRefreshView):
    """
    Takes a refresh type JSON web token and returns an access type JSON web
    token if the refresh token is valid.
    """
