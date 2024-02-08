import pytest

from invoicing.utils import generate_reference_number


@pytest.mark.parametrize(
    "identifier, expected",
    [
        (118, "28251187"),
        ("123456", "28251234568"),
        (999, "28259998"),
    ],
)
def test_generate_reference_number(identifier, expected):
    assert generate_reference_number(identifier) == expected
