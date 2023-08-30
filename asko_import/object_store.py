from collections import defaultdict
from typing import Optional

from application_form.enums import ApplicationType
from application_form.models import ApartmentReservation


class ObjectStore:
    """Contains IDs of already imported objects grouped by their models."""

    data = defaultdict(dict)

    def has(self, model, asko_id):
        return asko_id in self.data[model]

    def get_id(self, model, asko_id):
        try:
            return self.data[model][asko_id]
        except KeyError:
            raise KeyError(f"{model.__name__} asko_id={asko_id} not saved")

    def get_objects(self, model):
        return model.objects.filter(pk__in=self.get_ids(model))

    def get_ids(self, model):
        return self.data[model].values()

    def put(self, asko_id, instance, replace=False):
        model = type(instance)
        if self.has(model, asko_id) and not replace:
            raise KeyError(f"{model.__name__} asko_id={asko_id} already saved")
        self.data[model][asko_id] = instance.pk

    def get_hitas_apartment_uuids(self):
        hitas_types = [ApplicationType.HITAS, ApplicationType.PUOLIHITAS]
        return self.get_apartment_uuids_by_types(hitas_types)

    def get_haso_apartment_uuids(self):
        return self.get_apartment_uuids_by_types([ApplicationType.HASO])

    def get_apartment_uuids_by_types(self, types):
        all = self.get_objects(ApartmentReservation)
        res = all.filter(application_apartment__application__type__in=types)
        return res.values_list("apartment_uuid", flat=True).distinct()

    def clear(self):
        self.data.clear()


def get_object_store() -> ObjectStore:
    global _object_store
    if _object_store is None:
        _object_store = ObjectStore()
    return _object_store


_object_store: Optional[ObjectStore] = None
