"""
Test cases for asko_import models.
"""

from asko_import.models import AsKoLink

EXPECTED_INDEX_FIELDS = {
    ("object_type", "asko_id", "object_id_int"),
    ("object_type", "asko_id", "object_id_uuid"),
}


def test_asko_link_defines_composite_indexes_with_meta_indexes():
    """
    - AsKoLink declares its composite indexes with Meta.indexes.
    - Exactly the two expected field tuples are indexed.
    """
    index_fields = {tuple(index.fields) for index in AsKoLink._meta.indexes}

    assert index_fields == EXPECTED_INDEX_FIELDS
    assert len(AsKoLink._meta.indexes) == len(EXPECTED_INDEX_FIELDS)
