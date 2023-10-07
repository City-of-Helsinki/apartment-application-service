import enum
import logging
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Mapping, Tuple, Type

from django.db import models

from application_form.models.application import Applicant
from invoicing.models import ApartmentInstallment, ProjectInstallmentTemplate

from .logger import LOG

RowType = Mapping[str, object]
KeyValue = Tuple[object, ...]


@dataclass(frozen=True)
class UniqueKey:
    fields: Tuple[str, ...]
    log_duplicates: bool = True

    def get_value(self, row: RowType) -> KeyValue:
        return tuple(row[x] for x in self.fields)

    def __str__(self):
        return f"({', '.join(self.fields)})"


def make_key(*fields: str, log_duplicates: bool = True) -> UniqueKey:
    return UniqueKey(fields=fields, log_duplicates=log_duplicates)


UNIQUE_KEYS_BY_MODEL: Dict[Type[models.Model], List[UniqueKey]] = {
    ApartmentInstallment: [make_key("apartment_reservation", "type")],
    Applicant: [make_key("id", log_duplicates=False)],
    ProjectInstallmentTemplate: [make_key("project_uuid", "type")],
}

REQUIRED_FIELDS_BY_MODEL: Dict[Type[models.Model], List[str]] = {
    ApartmentInstallment: ["apartment_reservation", "reference_number"],
}


class IssueType(enum.Enum):
    DUPLICATE_KEY = "duplicate key"
    MISSING_VALUE = "missing value"


class DataIssue:
    def __init__(self, issue_type, model, row, log=True):
        self.issue_type: IssueType = issue_type
        self.model = model
        self.row: RowType = row
        self.log: bool = log

    def get_details(self) -> str:
        return ""

    def __str__(self):
        return f"{self.issue_type}: {self.row}"


class DuplicateKeyDataIssue(DataIssue):
    def __init__(self, key, key_value, model, row, other_row_id, log=True):
        self.key = key
        self.key_value = key_value
        self.other_row_id = other_row_id
        super().__init__(IssueType.DUPLICATE_KEY, model, row, log=log)

    def get_details(self) -> str:
        return (
            f"asko_id={self.other_row_id} already has "
            f"key {self.key}={self.key_value}.\n"
            f"row = {_redact(self.row)}"
        )


class MissingValueDataIssue(DataIssue):
    def __init__(self, field, model, row, log=True):
        self.field = field
        super().__init__(IssueType.MISSING_VALUE, model, row, log=log)

    def get_details(self) -> str:
        return f"Missing '{self.field}' value.\nrow = {_redact(self.row)}"


def _redact(row: RowType) -> RowType:
    return {k: v for k, v in row.items() if k in ALLOWED_ROW_FIELDS}


ALLOWED_ROW_FIELDS = {
    "due_date",
    "invoice_number",
    "value",
    "type",
    "customerid",
}


class IssueList:
    def __init__(self, issues: Iterable[DataIssue]) -> None:
        self.issues = list(issues)

    def __bool__(self):
        return bool(self.issues)

    def __iter__(self) -> Iterator[DataIssue]:
        return iter(self.issues)

    def log(self, logger=LOG, level=logging.WARNING):
        for i in self.issues:
            if i.log:
                if i.issue_type == IssueType.DUPLICATE_KEY:
                    logger.log(level, "Duplicate key: %s", i.get_details())
                elif i.issue_type == IssueType.MISSING_VALUE:
                    logger.log(level, "Missing value: %s", i.get_details())
                else:
                    issue = i.issue_type.name
                    logger.log(level, "%s issue: %s", issue, i.get_details())


class DataIssueChecker:
    """
    Checks AsKo data for known problems.

    The issues found are returned as IssueList.  The caller can then
    decide what to do with the issues, e.g. log them and skip the
    problematic rows or stop the processing.
    """

    def __init__(self, model: Type[models.Model]) -> None:
        self.model = model
        self.unique_keys = UNIQUE_KEYS_BY_MODEL.get(model, [])
        self.key_values_map: Dict[UniqueKey, Dict[KeyValue, int]] = {
            k: {} for k in self.unique_keys
        }

    def check(self, row: RowType) -> IssueList:
        return IssueList(self._check_all(row))

    def _check_all(self, row: RowType) -> Iterator[DataIssue]:
        required_fields_issues = list(self.check_required_fields(row))
        yield from required_fields_issues

        if required_fields_issues:
            return

        yield from self.check_duplicate_keys(row)

    def check_duplicate_keys(self, row: RowType) -> Iterator[DataIssue]:
        for key in self.unique_keys:
            values_map = self.key_values_map[key]
            key_value = key.get_value(row)
            other_row_id = values_map.get(key_value)  # row with same key value
            if other_row_id:
                yield DuplicateKeyDataIssue(
                    key,
                    key_value,
                    self.model,
                    row,
                    other_row_id,
                    log=key.log_duplicates,
                )
            else:
                values_map[key_value] = int(row["id"])  # type: ignore

    def check_required_fields(self, row: RowType) -> Iterator[DataIssue]:
        for field in REQUIRED_FIELDS_BY_MODEL.get(self.model, []):
            if not row.get(field):
                yield MissingValueDataIssue(field, self.model, row)
