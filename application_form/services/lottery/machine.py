import uuid
from django.utils.translation import ugettext_lazy as _

from apartment.elastic.queries import get_apartment_uuids, get_projects
from apartment.enums import OwnershipType
from application_form.exceptions import ProjectDoesNotHaveApplicationsException
from application_form.models import Application
from application_form.services.lottery.haso import _distribute_haso_apartments
from application_form.services.lottery.hitas import _distribute_hitas_apartments


def distribute_apartments(project_uuid: uuid.UUID) -> None:
    apartment_uuids = get_apartment_uuids(project_uuid)
    application_count = Application.objects.filter(
        application_apartments__apartment_uuid__in=apartment_uuids
    ).count()
    if application_count == 0:
        raise ProjectDoesNotHaveApplicationsException()

    project = get_projects(project_uuid)[0]
    if project.project_ownership_type.lower() == OwnershipType.HASO.value:
        _distribute_haso_apartments(project_uuid)
    elif project.project_ownership_type.lower() in [
        OwnershipType.HITAS.value,
        OwnershipType.HALF_HITAS.value,
    ]:
        _distribute_hitas_apartments(project_uuid)
    else:
        raise NotImplementedError(
            _(
                "The apartments of project cannot distribute by the given ownership"
                "type: {0}"
            ).format(project.project_ownership_type)
        )
