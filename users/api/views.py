from copy import copy
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db.models import Model
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from rest_framework import mixins, status
from rest_framework.exceptions import NotAuthenticated, PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from typing import Optional, Union

from audit_log import audit_logging
from audit_log.enums import Operation, Status
from users.api.permissions import IsCreatingOrAuthenticated
from users.api.serializers import MaskedTokenObtainPairSerializer, ProfileSerializer
from users.masking import mask_string, mask_uuid, unmask_uuid
from users.models import Profile

MASKED_ID_PARAMETER = OpenApiParameter(
    name="id",
    type={"type": "string"},
    location=OpenApiParameter.PATH,
    required=True,
    description="A masked UUID string identifying this profile.",
)


@extend_schema_view(
    create=extend_schema(responses=ProfileSerializer.CreateResponseSerializer, auth=[]),
    retrieve=extend_schema(parameters=[MASKED_ID_PARAMETER]),
    update=extend_schema(parameters=[MASKED_ID_PARAMETER]),
    destroy=extend_schema(parameters=[MASKED_ID_PARAMETER]),
)
class ProfileViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [IsCreatingOrAuthenticated]
    http_method_names = ["get", "post", "put", "delete"]
    method_to_operation = {
        "POST": Operation.CREATE,
        "GET": Operation.READ,
        "PUT": Operation.UPDATE,
        "DELETE": Operation.DELETE,
    }

    def permission_denied(self, request, message=None, code=None):
        try:
            super().permission_denied(request, message, code)
        except (NotAuthenticated, PermissionDenied):
            actor = self._get_actor(request)
            operation = self.method_to_operation[request.method]
            target = self._get_target(request)
            audit_logging.log(actor, operation, target, Status.FORBIDDEN)
            raise

    def initial(self, request, *args, **kwargs):
        if self.lookup_field in self.kwargs:
            self.kwargs[self.lookup_field] = unmask_uuid(self.kwargs[self.lookup_field])
        super().initial(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        response = super(ProfileViewSet, self).retrieve(request, *args, **kwargs)
        actor = self._get_actor(request)
        target = self.get_object()
        audit_logging.log(actor, Operation.READ, target)
        return response

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        credentials = self._create_credentials(serializer.instance.user)
        return Response(credentials, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        super().perform_create(serializer)
        audit_logging.log(
            self._get_actor(self.request),
            Operation.CREATE,
            serializer.instance,
        )

    def perform_update(self, serializer):
        super().perform_update(serializer)
        audit_logging.log(
            self._get_actor(self.request),
            Operation.UPDATE,
            serializer.instance,
        )

    def perform_destroy(self, instance):
        # Actor or target (or both) may be gone after super().perform_destroy
        actor = copy(self._get_actor(self.request))
        target = copy(instance)
        super().perform_destroy(instance)
        audit_logging.log(actor, Operation.DELETE, target)

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

    def _get_actor(self, request: Request) -> Union[Profile, AnonymousUser]:
        return getattr(request.user, "profile", request.user)

    def _get_target(self, request: Request) -> Optional[Model]:
        profile_uuid = self.kwargs.get(self.lookup_field, None)
        return Profile.objects.filter(pk=profile_uuid).first()


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

    serializer_class = MaskedTokenObtainPairSerializer


@extend_schema_view(post=extend_schema(summary="Refresh access token"))
class MaskedTokenRefreshView(TokenRefreshView):
    """
    Takes a refresh type JSON web token and returns an access type JSON web
    token if the refresh token is valid.
    """
