import importlib
import json
import sys

import pytest

# E2E tooling at the repo root; excluded from built images by .dockerignore.
django_dedup_fixture = pytest.importorskip("django_dedup_fixture")
dedup_user_key_values = django_dedup_fixture.dedup_user_key_values
main = django_dedup_fixture.main


def _ukv(pk, user, key, value):
    """
    Build a users.userkeyvalue fixture item.

            Parameters:
                    pk (int): Primary key
                    user (int): User foreign key
                    key (str): Key field
                    value (str): Value field

            Returns:
                    item (dict): Fixture item
    """
    return {
        "model": "users.userkeyvalue",
        "pk": pk,
        "fields": {"user": user, "key": key, "value": value},
    }


def test_dedup_removes_duplicate_user_key_values_keeping_first():
    """
    - rows with identical user, key and value are deduplicated
    - the first occurrence is kept
    - the number of removed rows is returned
    """
    items = [_ukv(1, 1, "k", "v"), _ukv(2, 1, "k", "v"), _ukv(3, 1, "k", "v")]

    kept, skipped = dedup_user_key_values(items)

    assert kept == [items[0]]
    assert skipped == 2


def test_dedup_keeps_user_key_values_differing_in_any_field():
    """
    - rows differing in user, key or value are all kept
    """
    items = [
        _ukv(1, 1, "k", "v"),
        _ukv(2, 2, "k", "v"),
        _ukv(3, 1, "other", "v"),
        _ukv(4, 1, "k", "other"),
    ]

    kept, skipped = dedup_user_key_values(items)

    assert kept == items
    assert skipped == 0


def test_dedup_leaves_other_models_untouched():
    """
    - identical items of other models are not deduplicated
    - item order is preserved
    """
    other = {"model": "users.user", "pk": 1, "fields": {"key": "k"}}
    items = [other, _ukv(1, 1, "k", "v"), dict(other)]

    kept, skipped = dedup_user_key_values(items)

    assert kept == items
    assert skipped == 0


def test_dedup_empty_fixture():
    """
    - an empty fixture yields an empty result and no removals
    """
    assert dedup_user_key_values([]) == ([], 0)


def test_main_writes_deduplicated_fixture(tmp_path, capsys):
    """
    - main reads the input file and writes the deduplicated output file
    - a summary is printed to stderr
    - exit code is 0
    """
    src = tmp_path / "in.json"
    dst = tmp_path / "out.json"
    src.write_text(json.dumps([_ukv(1, 1, "k", "v"), _ukv(2, 1, "k", "v")]))

    exit_code = main([str(src), str(dst)])

    assert exit_code == 0
    assert json.loads(dst.read_text()) == [_ukv(1, 1, "k", "v")]
    assert "1 objects kept, 1 duplicates removed" in capsys.readouterr().err


def test_main_rejects_wrong_argument_count(tmp_path, capsys):
    """
    - main returns a non-zero exit code when not given exactly two paths
    - usage is printed to stderr
    - no output file is written
    """
    src = tmp_path / "in.json"
    src.write_text("[]")

    exit_code = main([str(src)])

    assert exit_code != 0
    assert "Usage" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == [src]


def test_import_has_no_side_effects(monkeypatch):
    """
    - importing the module does not read sys.argv or touch files
    - regression: pytest --doctest-modules imports the module with pytest's
      own argv, which previously crashed with FileNotFoundError
    """
    monkeypatch.setattr(sys, "argv", ["pytest", "-ra", "-vvv"])

    importlib.reload(django_dedup_fixture)
