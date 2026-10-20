import json
import re
import uuid
from pathlib import Path

import pytest

# E2E tooling at the repo root; not part of built images, so skip when absent.
BASELINE_PATH = (
    Path(__file__).resolve().parents[2] / "e2e" / "fixtures" / "baseline.json"
)
if not BASELINE_PATH.is_file():
    pytest.skip(
        f"E2E baseline fixture not found at {BASELINE_PATH}",
        allow_module_level=True,
    )

KEY_PATTERN = re.compile(r"^[a-z0-9-]+$")
UUID_PREFIX = "e2e0"
HOUSING_COMPANY_PREFIX = "E2E "
# Term names of the Drupal ownership_type vocabulary (taxonomy_term_field_data).
DRUPAL_OWNERSHIP_TYPES = {"HASO", "Hitas", "Puolihitas"}


@pytest.fixture(scope="module")
def baseline():
    """
    Load the committed e2e baseline fixture.

            Returns:
                    data (dict): Parsed baseline.json content
    """
    with BASELINE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture(scope="module")
def projects(baseline):
    """
    Return the projects list of the baseline fixture.

            Parameters:
                    baseline (dict): Parsed baseline.json content

            Returns:
                    projects (list): Project entries
    """
    return baseline["projects"]


@pytest.fixture(scope="module")
def apartments(projects):
    """
    Return all apartment entries across all projects.

            Parameters:
                    projects (list): Project entries

            Returns:
                    apartments (list): Apartment entries
    """
    return [apartment for project in projects for apartment in project["apartments"]]


def test_baseline_has_description_and_projects(baseline):
    """
    - "description" is a non-empty string
    - "projects" is a non-empty list
    """
    assert isinstance(baseline.get("description"), str)
    assert baseline["description"].strip()
    assert isinstance(baseline.get("projects"), list)
    assert baseline["projects"]


def test_every_project_has_non_empty_apartment_list(projects):
    """
    - every project has an "apartments" list with at least one entry
    """
    for project in projects:
        assert isinstance(project.get("apartments"), list), project.get("key")
        assert project["apartments"], project.get("key")


def test_project_keys_are_valid_and_unique(projects):
    """
    - every project key matches ^[a-z0-9-]+$
    - project keys are unique
    """
    keys = [project.get("key") for project in projects]

    for key in keys:
        assert isinstance(key, str) and KEY_PATTERN.match(key), key
    assert len(keys) == len(set(keys))


def test_apartment_keys_are_valid_and_unique_across_file(apartments):
    """
    - every apartment key matches ^[a-z0-9-]+$
    - apartment keys are unique across all projects
    """
    keys = [apartment.get("key") for apartment in apartments]

    for key in keys:
        assert isinstance(key, str) and KEY_PATTERN.match(key), key
    assert len(keys) == len(set(keys))


def test_uuids_are_canonical_lowercase_with_e2e_prefix(projects, apartments):
    """
    - every project and apartment uuid parses as a UUID
    - every uuid equals its canonical lowercase string form
    - every uuid starts with "e2e0"
    """
    for entry in [*projects, *apartments]:
        value = entry.get("uuid")
        assert isinstance(value, str), entry.get("key")
        assert str(uuid.UUID(value)) == value, value
        assert value.startswith(UUID_PREFIX), value


def test_uuids_are_unique_across_projects_and_apartments(projects, apartments):
    """
    - no uuid is shared between any two projects or apartments
    """
    uuids = [entry["uuid"] for entry in [*projects, *apartments]]

    assert len(uuids) == len(set(uuids))


def test_ownership_types_are_drupal_term_names(projects):
    """
    - every project ownership_type is an existing Drupal ownership_type term name
    """
    for project in projects:
        assert project.get("ownership_type") in DRUPAL_OWNERSHIP_TYPES, project["key"]


def test_projects_have_drupal_required_fields(projects):
    """
    - housing_company starts with "E2E "
    - street_address is a non-empty string
    """
    for project in projects:
        housing_company = project.get("housing_company")
        street_address = project.get("street_address")

        assert isinstance(housing_company, str), project["key"]
        assert housing_company.startswith(HOUSING_COMPANY_PREFIX), project["key"]
        assert isinstance(street_address, str), project["key"]
        assert street_address.strip(), project["key"]


def test_apartment_numbers_are_non_empty_and_unique_within_project(projects):
    """
    - every apartment_number is a non-empty string
    - apartment numbers are unique within their project
    """
    for project in projects:
        numbers = [
            apartment.get("apartment_number") for apartment in project["apartments"]
        ]

        for number in numbers:
            assert isinstance(number, str) and number.strip(), project["key"]
        assert len(numbers) == len(set(numbers)), project["key"]


def test_baseline_covers_required_scenarios(projects):
    """
    - at least one HASO project has at least 4 apartments
    - at least one Hitas project has at least 2 apartments
    """

    def has_project(ownership_type, min_apartments):
        """
        Return whether a project of the given type has enough apartments.

                Parameters:
                        ownership_type (str): Drupal ownership_type term name
                        min_apartments (int): Minimum apartment count

                Returns:
                        found (bool): True if such a project exists
        """
        return any(
            project["ownership_type"] == ownership_type
            and len(project["apartments"]) >= min_apartments
            for project in projects
        )

    assert has_project("HASO", 4)
    assert has_project("Hitas", 2)


def test_optional_numeric_apartment_fields_have_correct_types(apartments):
    """
    - living_area, if present, is an int or float (not bool)
    - floor, if present, is an int (not bool)
    """
    for apartment in apartments:
        if "living_area" in apartment:
            living_area = apartment["living_area"]
            assert isinstance(living_area, (int, float)), apartment["key"]
            assert not isinstance(living_area, bool), apartment["key"]
        if "floor" in apartment:
            floor = apartment["floor"]
            assert isinstance(floor, int), apartment["key"]
            assert not isinstance(floor, bool), apartment["key"]
