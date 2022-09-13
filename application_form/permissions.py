from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication, permissions
from rest_framework.authentication import get_authorization_header
from rest_framework.exceptions import AuthenticationFailed


class DrupalServerUser(AnonymousUser):
    @property
    def is_authenticated(self):
        # Always return True. This is a way to tell if
        # the user has been authenticated in permissions
        return True


class IsDrupalServer(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and isinstance(request.user, DrupalServerUser))


class DrupalAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            raise AuthenticationFailed("Invalid token header. No credentials provided.")

        elif len(auth) > 2:
            raise AuthenticationFailed(
                "Invalid token header. Token string should not contain spaces."
            )

        token = auth[1].decode()

        if not (settings.DRUPAL_SERVER_AUTH_TOKEN == token):
            raise AuthenticationFailed(
                "You do not have permission to access this resource"
            )

        user = DrupalServerUser()

        return user, None
