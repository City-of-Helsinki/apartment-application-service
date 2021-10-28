from django.utils.translation import ugettext_lazy as _

from apartment.enums import OwnershipType


def map_project_ownership_type(ownership_type: str):
    ownership_type = ownership_type.upper()
    if ownership_type == "HASO":
        return OwnershipType.HASO
    if ownership_type == "HITAS":
        return OwnershipType.HITAS
    if ownership_type == "PUOLIHITAS":
        return OwnershipType.HALF_HITAS
    raise ValueError(_("Could not map the ownership_type %s") % ownership_type)
