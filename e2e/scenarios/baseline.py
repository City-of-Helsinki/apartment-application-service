"""
Load and validate the e2e baseline fixture (e2e/fixtures/baseline.json).

The baseline lists the Drupal projects and apartments the e2e stack always
contains. Scenarios resolve apartments through it instead of querying the
Drupal search API, so seeding depends only on this file.

Imports nothing from Django, so it is usable without a configured project.
"""

import json
import os
import re
import uuid
from pathlib import Path

BASELINE_ENV_VAR = "E2E_BASELINE_FILE"
# e2e/fixtures/baseline.json, relative to this file (e2e/scenarios/).
DEFAULT_BASELINE_PATH = Path(__file__).resolve().parents[1] / "fixtures/baseline.json"

KEY_PATTERN = re.compile(r"[a-z0-9-]+")
UUID_PREFIX = "e2e0"
HOUSING_COMPANY_PREFIX = "E2E "
# Term names of the Drupal ownership_type vocabulary.
OWNERSHIP_TYPES = ("HASO", "Hitas", "Puolihitas")


class Baseline:
    """
    Validated baseline content with lookups by project and apartment key.
    """

    def __init__(self, data):
        """
        Index the projects and apartments of validated baseline data.

                Parameters:
                        data (dict): Baseline content that passed
                        validate_baseline
        """
        self.description = data["description"]
        self.projects = data["projects"]
        self._projects = {project["key"]: project for project in self.projects}
        self._apartments = {
            apartment["key"]: {
                **apartment,
                "project_uuid": project["uuid"],
                "project_key": project["key"],
            }
            for project in self.projects
            for apartment in project["apartments"]
        }

    def project(self, key):
        """
        Return the project with the given key.

                Parameters:
                        key (str): Project key, e.g. "haso"

                Returns:
                        project (dict): The baseline project entry

                Raises:
                        KeyError: If no project has the key
        """
        return self._projects[key]

    def apartment(self, key):
        """
        Return the apartment with the given key, augmented with its project.

                Parameters:
                        key (str): Apartment key, e.g. "haso-a1"

                Returns:
                        apartment (dict): Copy of the baseline apartment entry
                        plus "project_uuid" and "project_key"

                Raises:
                        KeyError: If no apartment has the key
        """
        return dict(self._apartments[key])


def _is_non_blank_string(value):
    """
    Return whether a value is a string with non-whitespace content.

            Parameters:
                    value: Any value

            Returns:
                    result (bool): True for a non-blank string
    """
    return isinstance(value, str) and bool(value.strip())


def _key_errors(where, value):
    """
    Return errors for an invalid project or apartment key.

            Parameters:
                    where (str): Location of the entry, e.g. "projects[0]"
                    value: The key value

            Returns:
                    errors (list[str]): Empty if the key is valid
    """
    if isinstance(value, str) and KEY_PATTERN.fullmatch(value):
        return []
    return [f"{where}.key {value!r} must match ^[a-z0-9-]+$"]


def _uuid_errors(where, value):
    """
    Return errors for an invalid project or apartment uuid.

            Parameters:
                    where (str): Location of the entry, e.g. "projects[0]"
                    value: The uuid value

            Returns:
                    errors (list[str]): Empty if the uuid is canonical, lowercase
                    and starts with UUID_PREFIX
    """
    if not isinstance(value, str):
        return [f"{where}.uuid {value!r} must be a string"]
    try:
        canonical = str(uuid.UUID(value))
    except ValueError:
        return [f"{where}.uuid {value!r} is not a valid UUID"]
    if canonical != value:
        return [f"{where}.uuid {value!r} must be in canonical lowercase form"]
    if not value.startswith(UUID_PREFIX):
        return [f"{where}.uuid {value!r} must start with {UUID_PREFIX!r}"]
    return []


def _duplicate_errors(field, entries):
    """
    Return errors for values occurring more than once.

            Parameters:
                    field (str): Field name used in the messages
                    entries (list[tuple]): (location, value) pairs; values that
                    are not strings are ignored

            Returns:
                    errors (list[str]): One error per repeated occurrence
    """
    seen = {}
    errors = []
    for where, value in entries:
        if not isinstance(value, str):
            continue
        if value in seen:
            errors.append(f"{where}.{field} {value!r} duplicates {seen[value]}.{field}")
        else:
            seen[value] = where
    return errors


def _numeric_field_errors(where, apartment):
    """
    Return errors for the optional numeric fields of an apartment.

            Parameters:
                    where (str): Location of the apartment
                    apartment (dict): Apartment entry

            Returns:
                    errors (list[str]): living_area must be int/float and floor
                    an int when present; booleans are rejected
    """
    errors = []
    if "living_area" in apartment:
        value = apartment["living_area"]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{where}.living_area {value!r} must be a number")
    if "floor" in apartment:
        value = apartment["floor"]
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{where}.floor {value!r} must be an integer")
    return errors


def _apartment_errors(where, apartment):
    """
    Return errors of a single apartment entry.

            Parameters:
                    where (str): Location of the apartment
                    apartment: Apartment entry

            Returns:
                    errors (list[str]): Validation errors of the entry
    """
    if not isinstance(apartment, dict):
        return [f"{where} must be an object"]
    errors = _key_errors(where, apartment.get("key"))
    errors += _uuid_errors(where, apartment.get("uuid"))
    number = apartment.get("apartment_number")
    if not _is_non_blank_string(number):
        errors.append(f"{where}.apartment_number {number!r} must be a non-empty string")
    return errors + _numeric_field_errors(where, apartment)


def _project_field_errors(where, project):
    """
    Return errors of a project's own (non-apartment) fields.

            Parameters:
                    where (str): Location of the project
                    project (dict): Project entry

            Returns:
                    errors (list[str]): Validation errors of the fields
    """
    errors = _key_errors(where, project.get("key"))
    errors += _uuid_errors(where, project.get("uuid"))
    ownership_type = project.get("ownership_type")
    if ownership_type not in OWNERSHIP_TYPES:
        errors.append(
            f"{where}.ownership_type {ownership_type!r} must be one of "
            f"{', '.join(OWNERSHIP_TYPES)}"
        )
    company = project.get("housing_company")
    if not isinstance(company, str) or not company.startswith(HOUSING_COMPANY_PREFIX):
        errors.append(
            f"{where}.housing_company {company!r} must start with "
            f"{HOUSING_COMPANY_PREFIX!r}"
        )
    address = project.get("street_address")
    if not _is_non_blank_string(address):
        errors.append(f"{where}.street_address {address!r} must be a non-empty string")
    return errors


def _project_errors(where, project):
    """
    Return errors of a project entry and its apartments.

            Parameters:
                    where (str): Location of the project
                    project: Project entry

            Returns:
                    errors (list[str]): Validation errors of the project
    """
    if not isinstance(project, dict):
        return [f"{where} must be an object"]
    errors = _project_field_errors(where, project)
    apartments = project.get("apartments")
    if not isinstance(apartments, list) or not apartments:
        return errors + [f"{where}.apartments must be a non-empty list"]
    numbers = []
    for index, apartment in enumerate(apartments):
        apartment_where = f"{where}.apartments[{index}]"
        errors += _apartment_errors(apartment_where, apartment)
        if isinstance(apartment, dict):
            numbers.append((apartment_where, apartment.get("apartment_number")))
    return errors + _duplicate_errors("apartment_number", numbers)


def _entries(projects):
    """
    Return the locations of every project and apartment object.

            Parameters:
                    projects (list): Project entries

            Returns:
                    entries (tuple): (project entries, apartment entries), each a
                    list of (location, dict) pairs
    """
    project_entries = []
    apartment_entries = []
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            continue
        where = f"projects[{index}]"
        project_entries.append((where, project))
        apartments = project.get("apartments")
        if not isinstance(apartments, list):
            continue
        apartment_entries += [
            (f"{where}.apartments[{apartment_index}]", apartment)
            for apartment_index, apartment in enumerate(apartments)
            if isinstance(apartment, dict)
        ]
    return project_entries, apartment_entries


def _uniqueness_errors(projects):
    """
    Return errors for keys and uuids repeated across the file.

    Project keys are unique among projects, apartment keys among apartments,
    and uuids among all projects and apartments.

            Parameters:
                    projects (list): Project entries

            Returns:
                    errors (list[str]): Duplicate key and uuid errors
    """
    project_entries, apartment_entries = _entries(projects)

    def values(entries, field):
        """Return (location, value) pairs of a field."""
        return [(where, entry.get(field)) for where, entry in entries]

    return (
        _duplicate_errors("key", values(project_entries, "key"))
        + _duplicate_errors("key", values(apartment_entries, "key"))
        + _duplicate_errors("uuid", values(project_entries + apartment_entries, "uuid"))
    )


def validate_baseline(data):
    """
    Return every rule violation of baseline content without modifying it.

            Parameters:
                    data: Parsed baseline.json content

            Returns:
                    errors (list[str]): Human-readable errors; empty if valid
    """
    if not isinstance(data, dict) or not data:
        return ["baseline root must be a non-empty object"]
    errors = []
    if not _is_non_blank_string(data.get("description")):
        errors.append("description must be a non-empty string")
    projects = data.get("projects")
    if not isinstance(projects, list) or not projects:
        return errors + ["projects must be a non-empty list"]
    for index, project in enumerate(projects):
        errors += _project_errors(f"projects[{index}]", project)
    return errors + _uniqueness_errors(projects)


def load_baseline(path=None):
    """
    Load and validate the baseline file.

    The path is, in order of precedence: the argument, the E2E_BASELINE_FILE
    environment variable, or the committed e2e/fixtures/baseline.json.

            Parameters:
                    path (str | Path | None): Baseline file to load

            Returns:
                    baseline (Baseline): The validated baseline

            Raises:
                    FileNotFoundError: If the file does not exist
                    ValueError: If the file is not valid JSON or fails validation
    """
    if path is None:
        path = os.environ.get(BASELINE_ENV_VAR) or DEFAULT_BASELINE_PATH
    path = Path(path)
    with path.open(encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError as error:
            raise ValueError(f"Baseline {path} is not valid JSON: {error}") from error
    errors = validate_baseline(data)
    if errors:
        raise ValueError(f"Baseline {path} is invalid: {'; '.join(errors)}")
    return Baseline(data)
