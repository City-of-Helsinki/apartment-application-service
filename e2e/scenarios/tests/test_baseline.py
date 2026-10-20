import copy
import json
from pathlib import Path

import pytest

from e2e.scenarios.baseline import Baseline, load_baseline, validate_baseline

# E2E tooling at the repo root; not part of built images, so skip when absent.
BASELINE_PATH = (
    Path(__file__).resolve().parents[3] / "e2e" / "fixtures" / "baseline.json"
)
if not BASELINE_PATH.is_file():
    pytest.skip(
        f"E2E baseline fixture not found at {BASELINE_PATH}",
        allow_module_level=True,
    )

BASELINE_ENV_VAR = "E2E_BASELINE_FILE"


@pytest.fixture(scope="module")
def raw_baseline():
    """
    Load the committed e2e baseline fixture as plain JSON.

            Returns:
                    data (dict): Parsed baseline.json content
    """
    with BASELINE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def baseline_copy(raw_baseline):
    """
    Return a deep copy of the baseline that a test may mutate freely.

            Parameters:
                    raw_baseline (dict): Parsed baseline.json content

            Returns:
                    data (dict): Independent copy of the baseline
    """
    return copy.deepcopy(raw_baseline)


@pytest.fixture
def write_json(tmp_path):
    """
    Return a function writing JSON-serializable data to a temp file.

            Parameters:
                    tmp_path (Path): pytest temporary directory

            Returns:
                    write (callable): write(data, name="baseline.json") -> Path
    """

    def write(data, name="baseline.json"):
        """
        Write data as JSON and return the file path.

                Parameters:
                        data: JSON-serializable data
                        name (str): File name inside tmp_path

                Returns:
                        path (Path): Path of the written file
        """
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    return write


def _resolve(data, path):
    """
    Return the container holding the last path element and that element.

            Parameters:
                    data: Nested dict/list structure
                    path (tuple): Keys and indexes from the root

            Returns:
                    target (tuple): (container, last key or index)
    """
    container = data
    for part in path[:-1]:
        container = container[part]
    return container, path[-1]


def _set(path, value):
    """
    Return a mutator that sets a nested value.

            Parameters:
                    path (tuple): Keys and indexes from the root
                    value: Value to assign

            Returns:
                    mutate (callable): mutate(data) applying the change in place
    """

    def mutate(data):
        """Assign the value at the path."""
        container, last = _resolve(data, path)
        container[last] = value

    return mutate


def _delete(path):
    """
    Return a mutator that deletes a nested key.

            Parameters:
                    path (tuple): Keys and indexes from the root

            Returns:
                    mutate (callable): mutate(data) applying the change in place
    """

    def mutate(data):
        """Delete the key at the path."""
        container, last = _resolve(data, path)
        del container[last]

    return mutate


def _copy(source, target):
    """
    Return a mutator that copies one nested value over another.

            Parameters:
                    source (tuple): Path of the value to copy
                    target (tuple): Path to overwrite

            Returns:
                    mutate (callable): mutate(data) applying the change in place
    """

    def mutate(data):
        """Copy the source value to the target path."""
        source_container, source_last = _resolve(data, source)
        target_container, target_last = _resolve(data, target)
        target_container[target_last] = source_container[source_last]

    return mutate


def _assert_error_mentions(errors, *fragments):
    """
    Assert that one error message contains every fragment (case-insensitive).

            Parameters:
                    errors (list[str]): Messages returned by validate_baseline
                    *fragments (str): Texts expected in a single message
    """
    assert isinstance(errors, list)
    assert errors, "expected validation errors, got none"
    assert all(isinstance(error, str) and error for error in errors)
    lowered = [error.lower() for error in errors]
    assert any(
        all(fragment.lower() in error for fragment in fragments) for error in lowered
    ), f"no error mentions {fragments}: {errors}"


HASO_PROJECT = ("projects", 0)
HITAS_PROJECT = ("projects", 1)
HASO_A1 = (*HASO_PROJECT, "apartments", 0)
HASO_A2 = (*HASO_PROJECT, "apartments", 1)
HITAS_B1 = (*HITAS_PROJECT, "apartments", 0)

INVALID_CASES = [
    # description
    pytest.param(_delete(("description",)), ("description",), id="description-missing"),
    pytest.param(_set(("description",), ""), ("description",), id="description-empty"),
    pytest.param(
        _set(("description",), "   "), ("description",), id="description-blank"
    ),
    pytest.param(
        _set(("description",), 1), ("description",), id="description-not-string"
    ),
    # projects
    pytest.param(_delete(("projects",)), ("projects",), id="projects-missing"),
    pytest.param(_set(("projects",), []), ("projects",), id="projects-empty"),
    pytest.param(_set(("projects",), {}), ("projects",), id="projects-not-list"),
    pytest.param(
        _delete((*HASO_PROJECT, "apartments")),
        ("apartments",),
        id="apartments-missing",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "apartments"), []),
        ("apartments",),
        id="apartments-empty",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "apartments"), "A1"),
        ("apartments",),
        id="apartments-not-list",
    ),
    # project keys
    pytest.param(_set((*HASO_PROJECT, "key"), "Haso"), ("key",), id="key-uppercase"),
    pytest.param(_set((*HASO_PROJECT, "key"), "ha so"), ("key",), id="key-space"),
    pytest.param(_set((*HASO_PROJECT, "key"), "ha_so"), ("key",), id="key-underscore"),
    pytest.param(_set((*HASO_PROJECT, "key"), ""), ("key",), id="key-empty"),
    pytest.param(_set((*HASO_PROJECT, "key"), 1), ("key",), id="key-not-string"),
    pytest.param(_delete((*HASO_PROJECT, "key")), ("key",), id="key-missing"),
    pytest.param(
        _set((*HITAS_PROJECT, "key"), "haso"),
        ("key", "haso"),
        id="project-key-duplicate",
    ),
    # apartment keys
    pytest.param(
        _set((*HASO_A1, "key"), "HASO-A1"), ("key",), id="apartment-key-uppercase"
    ),
    pytest.param(_set((*HASO_A1, "key"), "haso.a1"), ("key",), id="apartment-key-dot"),
    pytest.param(_delete((*HASO_A1, "key")), ("key",), id="apartment-key-missing"),
    pytest.param(
        _set((*HASO_A2, "key"), "haso-a1"),
        ("key", "haso-a1"),
        id="apartment-key-duplicate-within-project",
    ),
    pytest.param(
        _set((*HITAS_B1, "key"), "haso-a1"),
        ("key", "haso-a1"),
        id="apartment-key-duplicate-across-projects",
    ),
    # uuids
    pytest.param(
        _set((*HASO_PROJECT, "uuid"), "not-a-uuid"), ("uuid",), id="uuid-unparseable"
    ),
    pytest.param(
        _set((*HASO_PROJECT, "uuid"), "E2E00001-0000-4000-8000-000000000001"),
        ("uuid",),
        id="uuid-uppercase",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "uuid"), "e2e00001000040008000000000000001"),
        ("uuid",),
        id="uuid-not-canonical",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "uuid"), "{e2e00001-0000-4000-8000-000000000001}"),
        ("uuid",),
        id="uuid-braced",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "uuid"), "12300001-0000-4000-8000-000000000001"),
        ("uuid",),
        id="uuid-wrong-prefix",
    ),
    pytest.param(
        _set((*HASO_A1, "uuid"), "00000000-0000-4000-8000-000000000101"),
        ("uuid",),
        id="apartment-uuid-wrong-prefix",
    ),
    pytest.param(_set((*HASO_A1, "uuid"), 123), ("uuid",), id="uuid-not-string"),
    pytest.param(_delete((*HASO_A1, "uuid")), ("uuid",), id="uuid-missing"),
    pytest.param(
        _copy((*HASO_PROJECT, "uuid"), (*HASO_A1, "uuid")),
        ("uuid",),
        id="uuid-duplicate-project-and-apartment",
    ),
    pytest.param(
        _copy((*HASO_A1, "uuid"), (*HITAS_B1, "uuid")),
        ("uuid",),
        id="uuid-duplicate-across-projects",
    ),
    pytest.param(
        _copy((*HASO_PROJECT, "uuid"), (*HITAS_PROJECT, "uuid")),
        ("uuid",),
        id="uuid-duplicate-projects",
    ),
    # ownership_type
    pytest.param(
        _set((*HASO_PROJECT, "ownership_type"), "haso"),
        ("ownership_type",),
        id="ownership-type-wrong-case",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "ownership_type"), "Asumisoikeus"),
        ("ownership_type",),
        id="ownership-type-unknown",
    ),
    pytest.param(
        _delete((*HASO_PROJECT, "ownership_type")),
        ("ownership_type",),
        id="ownership-type-missing",
    ),
    # housing_company
    pytest.param(
        _set((*HASO_PROJECT, "housing_company"), "Asumisoikeus Oy"),
        ("housing_company",),
        id="housing-company-no-prefix",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "housing_company"), "E2EAsumisoikeus Oy"),
        ("housing_company",),
        id="housing-company-prefix-without-space",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "housing_company"), "e2e Asumisoikeus Oy"),
        ("housing_company",),
        id="housing-company-prefix-lowercase",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "housing_company"), 1),
        ("housing_company",),
        id="housing-company-not-string",
    ),
    pytest.param(
        _delete((*HASO_PROJECT, "housing_company")),
        ("housing_company",),
        id="housing-company-missing",
    ),
    # street_address
    pytest.param(
        _set((*HASO_PROJECT, "street_address"), ""),
        ("street_address",),
        id="street-address-empty",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "street_address"), "  "),
        ("street_address",),
        id="street-address-blank",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "street_address"), None),
        ("street_address",),
        id="street-address-null",
    ),
    pytest.param(
        _delete((*HASO_PROJECT, "street_address")),
        ("street_address",),
        id="street-address-missing",
    ),
    # apartment_number
    pytest.param(
        _set((*HASO_A1, "apartment_number"), ""),
        ("apartment_number",),
        id="apartment-number-empty",
    ),
    pytest.param(
        _set((*HASO_A1, "apartment_number"), " "),
        ("apartment_number",),
        id="apartment-number-blank",
    ),
    pytest.param(
        _set((*HASO_A1, "apartment_number"), 1),
        ("apartment_number",),
        id="apartment-number-not-string",
    ),
    pytest.param(
        _delete((*HASO_A1, "apartment_number")),
        ("apartment_number",),
        id="apartment-number-missing",
    ),
    pytest.param(
        _set((*HASO_A2, "apartment_number"), "A1"),
        ("apartment_number", "A1"),
        id="apartment-number-duplicate-within-project",
    ),
    # living_area
    pytest.param(
        _set((*HASO_A1, "living_area"), "45.5"),
        ("living_area",),
        id="living-area-string",
    ),
    pytest.param(
        _set((*HASO_A1, "living_area"), True),
        ("living_area",),
        id="living-area-bool",
    ),
    pytest.param(
        _set((*HASO_A1, "living_area"), None),
        ("living_area",),
        id="living-area-null",
    ),
    # floor
    pytest.param(_set((*HASO_A1, "floor"), 1.5), ("floor",), id="floor-float"),
    pytest.param(_set((*HASO_A1, "floor"), "1"), ("floor",), id="floor-string"),
    pytest.param(_set((*HASO_A1, "floor"), False), ("floor",), id="floor-bool"),
    pytest.param(_set((*HASO_A1, "floor"), None), ("floor",), id="floor-null"),
]

VALID_VARIATIONS = [
    pytest.param(
        _copy((*HASO_A1, "apartment_number"), (*HITAS_B1, "apartment_number")),
        id="apartment-number-repeated-in-other-project",
    ),
    pytest.param(
        _set((*HASO_PROJECT, "ownership_type"), "Puolihitas"),
        id="ownership-type-puolihitas",
    ),
    pytest.param(_set((*HASO_A1, "living_area"), 45), id="living-area-int"),
    pytest.param(_delete((*HASO_A1, "living_area")), id="living-area-absent"),
    pytest.param(_set((*HASO_A1, "floor"), 0), id="floor-zero"),
    pytest.param(_set((*HASO_A1, "floor"), -1), id="floor-negative"),
    pytest.param(_delete((*HASO_A1, "floor")), id="floor-absent"),
]


def test_real_baseline_is_valid(raw_baseline):
    """
    - validate_baseline returns an empty list for the committed baseline
    """
    assert validate_baseline(raw_baseline) == []


def test_validate_baseline_does_not_mutate_input(raw_baseline, baseline_copy):
    """
    - validating leaves the given data unchanged
    """
    validate_baseline(baseline_copy)

    assert baseline_copy == raw_baseline


def test_real_baseline_covers_required_scenarios(raw_baseline):
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
            for project in raw_baseline["projects"]
        )

    assert has_project("HASO", 4)
    assert has_project("Hitas", 2)


@pytest.mark.parametrize("mutate,fragments", INVALID_CASES)
def test_validate_baseline_reports_rule_violation(baseline_copy, mutate, fragments):
    """
    - a baseline violating one rule yields at least one error message
    - one message names the offending field (and value where relevant)
    """
    mutate(baseline_copy)

    _assert_error_mentions(validate_baseline(baseline_copy), *fragments)


@pytest.mark.parametrize("mutate", VALID_VARIATIONS)
def test_validate_baseline_accepts_valid_variations(baseline_copy, mutate):
    """
    - edge cases allowed by the rules produce no errors
    """
    mutate(baseline_copy)

    assert validate_baseline(baseline_copy) == []


@pytest.mark.parametrize(
    "data",
    [
        pytest.param(None, id="null"),
        pytest.param([], id="list"),
        pytest.param("baseline", id="string"),
        pytest.param({}, id="empty-object"),
    ],
)
def test_validate_baseline_reports_non_object_root(data):
    """
    - a root that is not a populated object yields errors instead of raising
    """
    errors = validate_baseline(data)

    assert isinstance(errors, list)
    assert errors


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param("haso", id="project-string"),
        pytest.param(None, id="project-null"),
        pytest.param(["haso"], id="project-list"),
    ],
)
def test_validate_baseline_reports_malformed_project_entry(baseline_copy, entry):
    """
    - a project entry that is not an object yields errors instead of raising
    """
    baseline_copy["projects"].append(entry)

    errors = validate_baseline(baseline_copy)

    assert errors


def test_validate_baseline_reports_malformed_apartment_entry(baseline_copy):
    """
    - an apartment entry that is not an object yields errors instead of raising
    """
    baseline_copy["projects"][0]["apartments"].append("A5")

    errors = validate_baseline(baseline_copy)

    assert errors


def test_validate_baseline_reports_every_violation(baseline_copy):
    """
    - several independent violations are all reported, not only the first
    """
    baseline_copy["projects"][0]["ownership_type"] = "Unknown"
    baseline_copy["projects"][1]["street_address"] = ""

    errors = validate_baseline(baseline_copy)

    _assert_error_mentions(errors, "ownership_type")
    _assert_error_mentions(errors, "street_address")


def test_load_baseline_defaults_to_committed_file(monkeypatch, raw_baseline):
    """
    - without a path or env var the committed baseline is loaded
    - the result is a Baseline exposing the file's projects
    """
    monkeypatch.delenv(BASELINE_ENV_VAR, raising=False)

    baseline = load_baseline()

    assert isinstance(baseline, Baseline)
    assert baseline.projects == raw_baseline["projects"]


@pytest.mark.parametrize("as_str", [False, True], ids=["path", "str"])
def test_load_baseline_reads_given_path(monkeypatch, baseline_copy, write_json, as_str):
    """
    - an explicit path (Path or str) is loaded instead of the default file
    """
    monkeypatch.delenv(BASELINE_ENV_VAR, raising=False)
    baseline_copy["projects"][0]["housing_company"] = "E2E Explicit Oy"
    path = write_json(baseline_copy)

    baseline = load_baseline(str(path) if as_str else path)

    assert baseline.project("haso")["housing_company"] == "E2E Explicit Oy"


def test_load_baseline_reads_env_var_path(monkeypatch, baseline_copy, write_json):
    """
    - E2E_BASELINE_FILE overrides the default path when no path is given
    """
    baseline_copy["projects"][0]["housing_company"] = "E2E Env Oy"
    monkeypatch.setenv(BASELINE_ENV_VAR, str(write_json(baseline_copy)))

    baseline = load_baseline()

    assert baseline.project("haso")["housing_company"] == "E2E Env Oy"


def test_load_baseline_explicit_path_beats_env_var(
    monkeypatch, baseline_copy, write_json
):
    """
    - an explicit path takes precedence over E2E_BASELINE_FILE
    """
    env_data = copy.deepcopy(baseline_copy)
    env_data["projects"][0]["housing_company"] = "E2E Env Oy"
    baseline_copy["projects"][0]["housing_company"] = "E2E Explicit Oy"
    monkeypatch.setenv(BASELINE_ENV_VAR, str(write_json(env_data, "env.json")))
    explicit = write_json(baseline_copy, "explicit.json")

    baseline = load_baseline(explicit)

    assert baseline.project("haso")["housing_company"] == "E2E Explicit Oy"


def test_load_baseline_rejects_invalid_file(monkeypatch, baseline_copy, write_json):
    """
    - an invalid baseline raises ValueError
    - the message lists the validation errors
    """
    monkeypatch.delenv(BASELINE_ENV_VAR, raising=False)
    baseline_copy["projects"][0]["ownership_type"] = "Unknown"
    baseline_copy["projects"][1]["street_address"] = ""

    with pytest.raises(ValueError) as excinfo:
        load_baseline(write_json(baseline_copy))

    message = str(excinfo.value)
    assert "ownership_type" in message
    assert "street_address" in message


def test_load_baseline_rejects_invalid_env_var_file(
    monkeypatch, baseline_copy, write_json
):
    """
    - an invalid baseline referenced by E2E_BASELINE_FILE raises ValueError
    """
    baseline_copy["projects"][0]["uuid"] = "not-a-uuid"
    monkeypatch.setenv(BASELINE_ENV_VAR, str(write_json(baseline_copy)))

    with pytest.raises(ValueError):
        load_baseline()


def test_load_baseline_rejects_malformed_json(monkeypatch, tmp_path):
    """
    - a file that is not valid JSON raises ValueError
    """
    monkeypatch.delenv(BASELINE_ENV_VAR, raising=False)
    path = tmp_path / "baseline.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError):
        load_baseline(path)


def test_load_baseline_missing_path_raises(monkeypatch, tmp_path):
    """
    - a missing explicit path raises FileNotFoundError
    """
    monkeypatch.delenv(BASELINE_ENV_VAR, raising=False)

    with pytest.raises(FileNotFoundError):
        load_baseline(tmp_path / "missing.json")


def test_load_baseline_missing_env_var_path_raises(monkeypatch, tmp_path):
    """
    - a missing file referenced by E2E_BASELINE_FILE raises FileNotFoundError
    """
    monkeypatch.setenv(BASELINE_ENV_VAR, str(tmp_path / "missing.json"))

    with pytest.raises(FileNotFoundError):
        load_baseline()


@pytest.fixture
def baseline(monkeypatch):
    """
    Return the committed baseline loaded through load_baseline.

            Parameters:
                    monkeypatch: pytest monkeypatch fixture

            Returns:
                    baseline (Baseline): Loaded baseline
    """
    monkeypatch.delenv(BASELINE_ENV_VAR, raising=False)
    return load_baseline(BASELINE_PATH)


@pytest.mark.parametrize("index,key", [(0, "haso"), (1, "hitas")])
def test_project_lookup_returns_project(baseline, raw_baseline, index, key):
    """
    - project(key) returns the project dict of that key
    """
    expected = raw_baseline["projects"][index]

    project = baseline.project(key)

    assert project["key"] == key
    assert project["uuid"] == expected["uuid"]
    assert project["housing_company"] == expected["housing_company"]


@pytest.mark.parametrize(
    "project_index,apartment_index,key,project_key",
    [
        (0, 0, "haso-a1", "haso"),
        (0, 3, "haso-a4", "haso"),
        (1, 1, "hitas-b2", "hitas"),
    ],
)
def test_apartment_lookup_returns_augmented_apartment(
    baseline, raw_baseline, project_index, apartment_index, key, project_key
):
    """
    - apartment(key) returns every field of the baseline apartment
    - the result is augmented with its project's uuid and key
    """
    project = raw_baseline["projects"][project_index]
    expected = project["apartments"][apartment_index]

    apartment = baseline.apartment(key)

    for field, value in expected.items():
        assert apartment[field] == value
    assert apartment["project_uuid"] == project["uuid"]
    assert apartment["project_key"] == project_key


@pytest.mark.parametrize("key", ["missing", "haso-a1", "", "HASO"])
def test_project_lookup_unknown_key_raises_key_error(baseline, key):
    """
    - project() raises KeyError for unknown keys and apartment keys
    """
    with pytest.raises(KeyError):
        baseline.project(key)


@pytest.mark.parametrize("key", ["missing", "haso", "", "HASO-A1"])
def test_apartment_lookup_unknown_key_raises_key_error(baseline, key):
    """
    - apartment() raises KeyError for unknown keys and project keys
    """
    with pytest.raises(KeyError):
        baseline.apartment(key)
