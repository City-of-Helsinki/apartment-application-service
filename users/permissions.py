from rest_framework.permissions import BasePermission

from users.enums import Roles


class IsSalesperson(BasePermission):
    """
    Validate that the user has Salesperson role.
    """

    def has_permission(self, request, view):
        if (
            request.user
            and request.user.groups.filter(name__iexact=Roles.SALESPERSON.name).exists()
        ):
            return True
        return False
