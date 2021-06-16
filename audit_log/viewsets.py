from copy import copy
from django.contrib.auth.models import AnonymousUser
from django.db.models import Model
from rest_framework.viewsets import ModelViewSet
from typing import Optional, Union

from audit_log import audit_logging
from audit_log.enums import Operation, Status
from users.models import Profile


class AuditLoggingModelViewSet(ModelViewSet):
    method_to_operation = {
        "POST": Operation.CREATE,
        "GET": Operation.READ,
        "PUT": Operation.UPDATE,
        "PATCH": Operation.UPDATE,
        "DELETE": Operation.DELETE,
    }

    def permission_denied(self, request, message=None, code=None):
        audit_logging.log(
            self._get_actor(),
            self._get_operation(),
            self._get_target(),
            Status.FORBIDDEN,
        )
        super().permission_denied(request, message, code)

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        audit_logging.log(self._get_actor(), Operation.READ, self._get_target())
        return response

    def perform_create(self, serializer):
        super().perform_create(serializer)
        audit_logging.log(self._get_actor(), Operation.CREATE, serializer.instance)

    def perform_update(self, serializer):
        super().perform_update(serializer)
        audit_logging.log(self._get_actor(), Operation.UPDATE, serializer.instance)

    def perform_destroy(self, instance):
        actor = copy(self._get_actor())
        target = copy(instance)
        super().perform_destroy(instance)
        audit_logging.log(actor, Operation.DELETE, target)

    def _get_actor(self) -> Union[Profile, AnonymousUser]:
        return getattr(self.request.user, "profile", self.request.user)

    def _get_operation(self) -> Operation:
        return self.method_to_operation[self.request.method]

    def _get_target(self) -> Optional[Model]:
        target = None
        lookup_value = self.kwargs.get(self.lookup_field, None)
        if lookup_value is not None:
            target = self.queryset.model.objects.filter(
                **{self.lookup_field: lookup_value}
            ).first()
        return target or self.queryset.model()
