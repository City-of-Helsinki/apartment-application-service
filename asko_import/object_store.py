from typing import Optional

from application_form.enums import ApplicationType
from application_form.models import ApartmentReservation

from .models import AsKoLink


class ObjectStore:
    """Contains IDs of already imported objects grouped by their models."""

    def __init__(self):
        self._data = {}

    def for_model(self, model):
        data = self._data.get(model)
        if data is None:
            data = self._data[model] = {}
            data.update(AsKoLink.get_map_for_model(model))
        return data

    def has(self, model, asko_id):
        return int(asko_id) in self.for_model(model)

    def get_id(self, model, asko_id):
        try:
            return self.for_model(model)[int(asko_id)]
        except KeyError:
            raise KeyError(f"{model.__name__} asko_id={asko_id} not saved")

    def get_objects(self, model):
        return model.objects.filter(pk__in=self.get_ids(model))

    def get_ids(self, model):
        return self.for_model(model).values()

    def put(self, asko_id, instance, replace=False):
        model = type(instance)
        if self.has(model, asko_id) and not replace:
            raise KeyError(f"{model.__name__} asko_id={asko_id} already saved")
        self.for_model(model)[asko_id] = instance.pk
        AsKoLink.store(asko_id, instance)

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
        self._data.clear()


def get_object_store() -> ObjectStore:
    global _object_store
    if _object_store is None:
        _object_store = ObjectStore()
    return _object_store


_object_store: Optional[ObjectStore] = None
