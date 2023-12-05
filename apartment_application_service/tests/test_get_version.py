import contextlib
import os
from unittest.mock import patch

import pytest

from ..version import get_version

TEST_CASES = {
    "env-tag": (
        "382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365",
        "refs/tags/release-1.0.4",
        b"382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365",
        "release-1.0.4",
    ),
    "env-branch": (
        "382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365",
        "refs/heads/main",
        b"382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365",
        "382b1d3",
    ),
    "git-commit": (
        None,
        None,
        b"382b1d3\n",
        "382b1d3",
    ),
    "git-commit-spaces": (
        None,
        None,
        b"  382b1d3\n",
        "382b1d3",
    ),
    "env-tag-slash": (
        "382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365",
        "refs/tags/release/1.0.4",
        b"382b1d3ee9a4ee3c3a5c0c52f03ad2c7b7b5b365",
        "release_1.0.4",
    ),
}


@pytest.mark.parametrize("test_case", list(TEST_CASES))
@patch("apartment_application_service.version.subprocess.check_output")
def test_get_version(subprocess_check_output, test_case):
    (commit, ref, git_output, expected_result) = TEST_CASES[test_case]
    subprocess_check_output.return_value = git_output

    with commit_and_ref_in_env(commit, ref):
        result = get_version()

    assert result == expected_result


@patch("apartment_application_service.version.subprocess.check_output")
def test_get_version_git_fail(subprocess_check_output):
    subprocess_check_output.side_effect = Exception("git failed")

    with commit_and_ref_in_env(None, None):
        result = get_version()

    assert result == "UNKNOWN"


@contextlib.contextmanager
def commit_and_ref_in_env(commit, ref):
    values = {
        "OPENSHIFT_BUILD_COMMIT": commit,
        "OPENSHIFT_BUILD_REFERENCE": ref,
    }
    with modified_env(**values):
        yield


@contextlib.contextmanager
def modified_env(**values):
    old_values = {name: os.environ.get(name) for name in values.keys()}

    try:
        _set_env(**values)
        yield
    finally:
        _set_env(**old_values)


def _set_env(**values):
    for name, value in values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
