"""
Tests for ApartmentDocument Pydantic v2 model.

The Drupal Search API serializes most fields as strings (via SearchMapper::
getScalar). ApartmentDocument must coerce them to their declared Python types
(int, float, bool, datetime, UUID, list[str]) and, for typed Optional fields,
replace '' with None while emitting a logger.warning so Drupal-side data
quality issues can be diagnosed.
"""

import logging
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from apartment.elastic.documents import ApartmentDocument


def _minimal_payload(**overrides):
    """
    Build a minimal valid Drupal _source payload for ApartmentDocument.

    Only `project_id` and `project_uuid` are strictly required by the model.
    Callers override fields under test; other fields are left absent so
    their defaults exercise the Optional coercion paths.
    """
    payload = {
        "project_id": 42,
        "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "uuid": "11111111-2222-3333-4444-555555555555",
    }
    payload.update(overrides)
    return payload


class TestNumericCoercion:
    """String numerics from Drupal must be coerced to int / float."""

    def test_long_field_accepts_string_integer(self):
        """Long fields arriving as strings coerce to int."""
        doc = ApartmentDocument(**_minimal_payload(sales_price="250000"))

        assert doc.sales_price == 250000
        assert isinstance(doc.sales_price, int)

    def test_long_field_accepts_native_integer(self):
        """Long fields arriving as int stay int."""
        doc = ApartmentDocument(**_minimal_payload(sales_price=250000))

        assert doc.sales_price == 250000
        assert isinstance(doc.sales_price, int)

    def test_float_field_accepts_string_decimal(self):
        """Float fields arriving as decimal strings coerce to float."""
        doc = ApartmentDocument(**_minimal_payload(living_area="42.12"))

        assert doc.living_area == pytest.approx(42.12)
        assert isinstance(doc.living_area, float)

    def test_float_field_accepts_native_float(self):
        """Float fields arriving as float stay float."""
        doc = ApartmentDocument(**_minimal_payload(living_area=42.12))

        assert doc.living_area == pytest.approx(42.12)
        assert isinstance(doc.living_area, float)

    def test_required_long_field_accepts_string(self):
        """Required Long fields (project_id) coerce from string."""
        payload = _minimal_payload()
        payload["project_id"] = "42"

        doc = ApartmentDocument(**payload)

        assert doc.project_id == 42
        assert isinstance(doc.project_id, int)


class TestBooleanCoercion:
    """Drupal may emit native bools or '0'/'1' strings for boolean fields."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (True, True),
            (False, False),
            ("true", True),
            ("false", False),
            ("1", True),
            ("0", False),
        ],
    )
    def test_boolean_field_coerces_common_representations(self, raw, expected):
        """Booleans accept native bool, 'true'/'false', and '1'/'0'."""
        doc = ApartmentDocument(**_minimal_payload(has_balcony=raw))

        assert doc.has_balcony is expected


class TestDateCoercion:
    """asu_content_convert_datetime emits ISO-ish strings."""

    def test_date_field_accepts_iso_naive_string(self):
        """Naive ISO 8601 datetime strings parse into datetime."""
        doc = ApartmentDocument(
            **_minimal_payload(project_application_start_time="2024-04-01T12:00:00")
        )

        assert doc.project_application_start_time == datetime(2024, 4, 1, 12, 0, 0)

    def test_date_field_accepts_iso_with_timezone(self):
        """Timezone-aware ISO 8601 strings parse with tzinfo preserved."""
        doc = ApartmentDocument(
            **_minimal_payload(project_application_start_time="2024-04-01T12:00:00Z")
        )

        assert doc.project_application_start_time == datetime(
            2024, 4, 1, 12, 0, 0, tzinfo=timezone.utc
        )

    def test_date_field_accepts_native_datetime(self):
        """Native datetime values are passed through unchanged."""
        dt = datetime(2024, 4, 1, 12, 0, 0)
        doc = ApartmentDocument(**_minimal_payload(project_application_start_time=dt))

        assert doc.project_application_start_time == dt


class TestUuidFields:
    """
    uuid and project_uuid stay plain strings.

    The legacy elasticsearch_dsl schema declared them as Keyword; many
    consumers (views, DRF serializers, Django joins) compare them to plain
    strings pulled from the database. Keeping them as str avoids churn.
    """

    def test_project_uuid_is_string(self):
        doc = ApartmentDocument(**_minimal_payload())

        assert isinstance(doc.project_uuid, str)
        assert doc.project_uuid == "550e8400-e29b-41d4-a716-446655440000"

    def test_uuid_is_string(self):
        doc = ApartmentDocument(**_minimal_payload())

        assert isinstance(doc.uuid, str)


class TestMultiValueFields:
    """Keyword(multi=True) fields become list[str]."""

    def test_multi_field_defaults_to_empty_list_when_missing(self):
        doc = ApartmentDocument(**_minimal_payload())

        assert doc.project_construction_materials == []
        assert doc.project_heating_options == []
        assert doc.image_urls == []

    def test_multi_field_accepts_list_of_strings(self):
        urls = ["https://a.example/a.jpg", "https://a.example/b.jpg"]
        doc = ApartmentDocument(**_minimal_payload(image_urls=urls))

        assert doc.image_urls == urls

    def test_multi_field_coerces_empty_string_to_empty_list(self):
        """
        Drupal's SearchMapper emits '' for multi-valued fields that have no
        value (e.g. showing_times comes from a single getScalar call that
        returns '' when empty). The model must accept '' as shorthand for
        [] so ingestion doesn't fail on such payloads.
        """
        doc = ApartmentDocument(**_minimal_payload(showing_times=""))

        assert doc.showing_times == []

    def test_multi_field_empty_string_logs_warning(self, caplog):
        caplog.set_level(logging.WARNING, logger="apartment.elastic.documents")

        ApartmentDocument(**_minimal_payload(showing_times=""))

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        messages = " ".join(r.getMessage() for r in warnings)
        assert "showing_times" in messages


class TestRequiredFields:
    """Fields declared with required=True must be present."""

    @pytest.mark.parametrize(
        "missing_field",
        [
            "project_id",
            "project_uuid",
        ],
    )
    def test_missing_required_field_raises(self, missing_field):
        """
        Only project identifiers are strictly required. Other fields that
        were declared `required=True` in the legacy ES schema are kept
        Optional because Drupal routinely emits blank values for them during
        PRE_MARKETING states and the legacy elasticsearch_dsl class never
        enforced them at runtime.
        """
        payload = _minimal_payload()
        payload.pop(missing_field)

        with pytest.raises(ValidationError):
            ApartmentDocument(**payload)

    def test_required_numeric_field_rejects_empty_string(self):
        """
        Empty string in a required numeric field must fail validation rather
        than silently becoming None.
        """
        payload = _minimal_payload()
        payload["project_id"] = ""

        with pytest.raises(ValidationError):
            ApartmentDocument(**payload)


class TestExtraFields:
    """Unknown keys from Drupal should not break validation."""

    def test_extra_fields_are_ignored(self):
        payload = _minimal_payload(
            unknown_future_field="something",
            another_one=42,
        )

        doc = ApartmentDocument(**payload)

        assert not hasattr(doc, "unknown_future_field")
        assert not hasattr(doc, "another_one")


class TestEmptyStringCoercion:
    """
    Drupal's SearchMapper::getScalar returns '' for missing scalar values.
    Optional typed (non-string) fields must coerce '' to None and log a
    warning, so the data-quality issue is visible without breaking ingestion.
    """

    def test_empty_string_coerces_to_none_for_optional_int(self):
        doc = ApartmentDocument(**_minimal_payload(sales_price=""))

        assert doc.sales_price is None

    def test_empty_string_coerces_to_none_for_optional_float(self):
        doc = ApartmentDocument(**_minimal_payload(living_area=""))

        assert doc.living_area is None

    def test_empty_string_coerces_to_none_for_optional_bool(self):
        doc = ApartmentDocument(**_minimal_payload(has_balcony=""))

        assert doc.has_balcony is None

    def test_empty_string_coerces_to_none_for_optional_datetime(self):
        doc = ApartmentDocument(**_minimal_payload(project_application_start_time=""))

        assert doc.project_application_start_time is None

    def test_empty_string_stays_empty_string_for_optional_string(self):
        """Keyword (string) Optional fields keep '' as ''; it is a valid str."""
        doc = ApartmentDocument(**_minimal_payload(project_roof_material=""))

        assert doc.project_roof_material == ""

    def test_empty_string_in_typed_field_logs_warning(self, caplog):
        caplog.set_level(logging.WARNING, logger="apartment.elastic.documents")

        ApartmentDocument(**_minimal_payload(sales_price="", living_area=""))

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        messages = " ".join(r.getMessage() for r in warnings)
        assert "sales_price" in messages
        assert "living_area" in messages

    def test_empty_string_in_typed_field_logs_document_uuid(self, caplog):
        caplog.set_level(logging.WARNING, logger="apartment.elastic.documents")

        doc_uuid = "11111111-2222-3333-4444-555555555555"
        ApartmentDocument(**_minimal_payload(uuid=doc_uuid, sales_price=""))

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        messages = " ".join(r.getMessage() for r in warnings)
        assert doc_uuid in messages

    def test_empty_string_in_string_field_does_not_log(self, caplog):
        caplog.set_level(logging.WARNING, logger="apartment.elastic.documents")

        ApartmentDocument(**_minimal_payload(project_roof_material=""))

        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings == []


class TestComputedProperties:
    """Legacy behaviors of the class must be preserved."""

    def test_project_contract_combined_terms_joins_non_empty_strings(self):
        doc = ApartmentDocument(
            **_minimal_payload(
                project_contract_bill_of_sale_terms="A",
                project_contract_other_terms="B",
                project_contract_customer_document_handover="",
            )
        )

        assert doc.project_contract_combined_terms == "A\n\nB"

    def test_project_contract_combined_terms_skips_none(self):
        doc = ApartmentDocument(**_minimal_payload())

        assert doc.project_contract_combined_terms == ""

    def test_repr_contains_apartment_uuid(self):
        doc = ApartmentDocument(**_minimal_payload(apartment_address="Foo 1"))

        rendered = repr(doc)
        assert "ApartmentDocument" in rendered
        assert "uuid" in rendered
        assert "Foo 1" in rendered


class TestRealisticDrupalPayload:
    """
    Realistic payload mirroring SearchMapper output:
    - Numbers as strings (getScalar)
    - Money as ints (toCents)
    - Bools as native bool (getBoolean)
    - Dates as strings or '' (formatDateTime)
    """

    def test_realistic_payload_validates_with_coerced_types(self):
        payload = {
            "project_id": 42,
            "project_uuid": "550e8400-e29b-41d4-a716-446655440000",
            "project_ownership_type": "hitas",
            "project_housing_company": "Asunto Oy Testi",
            "project_holding_type": "CONDOMINIUM",
            "project_street_address": "Teststreet 1",
            "project_postal_code": "00100",
            "project_city": "Helsinki",
            "project_contract_business_id": "1234567-8",
            "project_district": "Kallio",
            "project_realty_id": "123-4-56-7",
            "project_new_development_status": "FOR_SALE",
            "project_new_housing": True,
            "project_apartment_count": "10",  # getScalar -> str
            "project_estimated_completion": "2025",
            "project_coordinate_lat": "60.17",
            "project_coordinate_lon": "24.94",
            "project_application_start_time": "2024-04-01T12:00:00",
            "project_application_end_time": "",
            "project_has_elevator": True,
            "project_has_sauna": False,
            "project_published": True,
            "uuid": "11111111-2222-3333-4444-555555555555",
            "apartment_address": "Teststreet 1 A 3",
            "floor": "2",
            "floor_max": "4",
            "living_area": "42.12",
            "room_count": 2,
            "sales_price": 25000000,
            "debt_free_sales_price": 25000000,
            "loan_share": 0,
            "housing_company_fee": 15000,
            "has_balcony": True,
            "has_terrace": False,
            "has_yard": False,
            "has_apartment_sauna": False,
            "image_urls": ["https://a.example/1.jpg"],
            "services": ["Koulu 500m"],
        }

        doc = ApartmentDocument(**payload)

        assert doc.project_id == 42
        assert doc.project_uuid == "550e8400-e29b-41d4-a716-446655440000"
        assert doc.project_apartment_count == 10
        assert doc.project_coordinate_lat == pytest.approx(60.17)
        assert doc.project_application_start_time == datetime(2024, 4, 1, 12, 0, 0)
        assert doc.project_application_end_time is None
        assert doc.floor == 2
        assert doc.floor_max == 4
        assert doc.living_area == pytest.approx(42.12)
        assert doc.sales_price == 25000000
        assert doc.has_balcony is True
        assert doc.image_urls == ["https://a.example/1.jpg"]
