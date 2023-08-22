from collections import defaultdict
from typing import Optional

from application_form.enums import ApplicationType
from application_form.models import ApartmentReservation


class ObjectStore:
    """Contains already imported objects grouped by their models."""

    data = defaultdict(dict)

    def get(self, model, asko_id):
        try:
            return self.data[model][asko_id]
        except KeyError:
            raise KeyError(f"{model.__name__} asko_id={asko_id} not saved")

    def get_instances(self, model):
        return self.data[model].values()

    def get_ids(self, model):
        return [o.pk for o in self.get_instances(model)]

    def put(self, asko_id, instance):
        model = type(instance)
        if model not in self.data or asko_id not in self.data[model]:
            self.data[model][asko_id] = instance

    def get_apartment_uuids(self):
        return set(r.apartment_uuid for r in self.data[ApartmentReservation].values())

    def get_hitas_apartment_uuids(self):
        return set(
            r.apartment_uuid
            for r in self.data[ApartmentReservation].values()
            if r.application_apartment.application.type
            in (ApplicationType.HITAS, ApplicationType.PUOLIHITAS)
        )

    def get_haso_apartment_uuids(self):
        return set(
            r.apartment_uuid
            for r in self.data[ApartmentReservation].values()
            if r.application_apartment.application.type == ApplicationType.HASO
        )

    def clear(self):
        self.data.clear()


def get_object_store() -> ObjectStore:
    global _object_store
    if _object_store is None:
        _object_store = ObjectStore()
    return _object_store


_object_store: Optional[ObjectStore] = None
