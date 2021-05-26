from rest_framework.permissions import IsAuthenticated


class IsCreatingOrAuthenticated(IsAuthenticated):
    def has_permission(self, request, view):
        return view.action == "create" or super().has_permission(request, view)
