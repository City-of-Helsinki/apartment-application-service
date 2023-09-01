from typing import Dict, List, Mapping, Optional, Tuple, Type

from django.db import models

from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate

KEY_TUPLES_BY_MODEL: Dict[Type[models.Model], List[Tuple[str, ...]]] = {
    ApartmentInstallment: [("apartment_reservation", "type")],
    ProjectInstallmentTemplate: [("project_uuid", "type")],
}


class DuplicateChecker:
    def __init__(self, model: Type[models.Model]) -> None:
        self.model = model
        self.key_tuples = KEY_TUPLES_BY_MODEL.get(model, [])
        self.key_values_list = [{} for _ in self.key_tuples]

    def check(self, row: Mapping[str, object]) -> Optional[str]:
        dupl: List[str] = []
        for (key_tuple, values) in zip(self.key_tuples, self.key_values_list):
            key = tuple(row[x] for x in key_tuple)
            item = values.get(key)
            if item:
                dupl.append(f"Item {item} already has key {key_tuple} = {key}")
            values[key] = row["id"]
        return " & ".join(dupl) if dupl else None
