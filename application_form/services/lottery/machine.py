from django.utils.translation import ugettext_lazy as _

from apartment.enums import OwnershipType
from apartment.models import Project
from application_form.services.lottery.haso import distribute_haso_apartments
from application_form.services.lottery.hitas import distribute_hitas_apartments


def distribute_apartments(project: Project) -> None:
    if project.ownership_type is OwnershipType.HASO:
        distribute_haso_apartments(project)
    elif project.ownership_type in [OwnershipType.HITAS, OwnershipType.HALF_HITAS]:
        distribute_hitas_apartments(project)
    else:
        raise NotImplementedError(
            _(
                "The apartments of project cannot distribute by the given ownership"
                "type: {0}"
            ).format(project.ownership_type)
        )
