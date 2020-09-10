from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_ilmoitin.dummy_context import COMMON_CONTEXT, dummy_context
from django_ilmoitin.registry import notifications
from unittest.mock import MagicMock

from apartment_application_service.consts import NotificationType

TEMPLATES = [
    (NotificationType.APPLICATION_CREATED, _("Application created")),
]

for template in TEMPLATES:
    notifications.register(template[0], template[1])

dummy_context.update(
    {
        COMMON_CONTEXT: {"created_at": timezone.now()},
        # TODO: pass more appropriate in-memory objects
        NotificationType.APPLICATION_CREATED: MagicMock(),
    }
)
