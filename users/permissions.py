from rest_framework.permissions import BasePermission


class IsSalesperson(BasePermission):
    """
    Validate that the user has Salesperson role.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_salesperson():
            return True
        return False
