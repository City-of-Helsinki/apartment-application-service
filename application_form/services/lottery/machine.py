import uuid
from django.contrib.auth import get_user_model
from django.utils.translation import ugettext_lazy as _

from apartment.elastic.queries import get_project
from apartment.enums import OwnershipType
from application_form.services.lottery.haso import _distribute_haso_apartments
from application_form.services.lottery.hitas import _distribute_hitas_apartments
from application_form.services.lottery.utils import (
    _validate_project_application_time_has_finished,
    _validate_project_has_applications,
)

User = get_user_model()


def distribute_apartments(project_uuid: uuid.UUID, user: User = None) -> None:
    _validate_project_has_applications(project_uuid)
    _validate_project_application_time_has_finished(project_uuid)

    project = get_project(project_uuid)
    if project.project_ownership_type.lower() == OwnershipType.HASO.value:
        _distribute_haso_apartments(project_uuid, user)
    elif project.project_ownership_type.lower() in [
        OwnershipType.HITAS.value,
        OwnershipType.PUOLIHITAS.value,
    ]:
        _distribute_hitas_apartments(project_uuid, user)
    else:
        raise NotImplementedError(
            _(
                "The apartments of project cannot distribute by the given ownership"
                "type: {0}"
            ).format(project.project_ownership_type)
        )
