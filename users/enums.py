from enum import Enum


class Roles(Enum):
    DRUPAL_SALESPERSON = "DRUPAL_SALESPERSON"
    DJANGO_SALESPERSON = "DJANGO_SALESPERSON"
    STAFF = "STAFF"


class UserKeyValueKeys(Enum):
    """Used to refer to keys in users.models.UserKeyValue.
    Saved here to avoid magic strings."""

    # project_uuid to exclude from sales report
    # TODO: REMOVE
    EXCLUDE_SALES_REPORT_PROJECT_UUID = "exclude_sales_report_project_uuid"
    INCLUDE_SALES_REPORT_PROJECT_UUID = "include_sales_report_project_uuid"
    pass
