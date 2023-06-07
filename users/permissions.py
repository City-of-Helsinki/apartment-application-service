from rest_framework.permissions import BasePermission


class IsDjangoSalesperson(BasePermission):
    """
    Validate that the user has Salesperson role.
    """

    def has_permission(self, request, view):
        if (
            request.user
            and request.user.is_authenticated
            and (request.user.is_django_salesperson() or request.user.is_staff_user())
        ):
            return True
        return False


class IsDrupalSalesperson(BasePermission):
    """
    Validate that the user has Salesperson role.
    """

    def has_permission(self, request, view):
        if (
            request.user
            and request.user.is_authenticated
            and (request.user.is_drupal_salesperson() or request.user.is_staff_user())
        ):
            return True
        return False
