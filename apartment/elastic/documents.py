"""
Pydantic v2 model mirroring the Elasticsearch apartment index schema.

Incoming data from the Drupal Search API is largely serialized as strings by
SearchMapper::getScalar (see drupal-asuntotuotanto). This module converts such
strings into the declared Python types (int, float, bool, datetime, UUID) so
downstream consumers (PDF generation, Oikotie/Etuovi mappers, DRF serializers)
work against properly typed values.

Optional typed fields that arrive as the empty string '' are coerced to None
and a warning is logged so Drupal-side data quality issues are visible.
Required typed fields arriving as '' fail validation explicitly.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from cost_index.utils import (
    current_right_of_occupancy_payment,
    reservation_right_of_occupancy_payment,
)

logger = logging.getLogger(__name__)

# Float and Long field names in ApartmentDocument (API may return '' or None)
# Kept as module-level constants for consumers (e.g. oikotie tests) that
# iterate over the numeric-field set.
APARTMENT_DOCUMENT_FLOAT_FIELDS = frozenset(
    {
        "project_coordinate_lat",
        "project_coordinate_lon",
        "project_site_area",
        "living_area",
    }
)
APARTMENT_DOCUMENT_LONG_FIELDS = frozenset(
    {
        "project_id",
        "project_apartment_count",
        "project_parkingplace_count",
        "floor",
        "floor_max",
        "room_count",
        "sales_price",
        "debt_free_sales_price",
        "loan_share",
        "price_m2",
        "housing_company_fee",
        "financing_fee",
        "maintenance_fee",
        "water_fee",
        "parking_fee",
        "stock_start_number",
        "stock_end_number",
        "right_of_occupancy_payment",
        "right_of_occupancy_fee",
        "right_of_occupancy_deposit",
        "release_payment",
        "field_index_adjusted_right_of_oc",
        "field_alteration_work",
    }
)


class ApartmentDocument(BaseModel):
    """
    In-memory representation of an apartment document from the Drupal Search
    API.

    Field types mirror the Elasticsearch index schema and are enforced via
    Pydantic v2. Unknown keys are ignored so forward-compatible additions on
    the Drupal side never break ingestion.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=False,
        # Drupal occasionally sends year/id-like fields as ints even though
        # the ES schema declares them as keywords (strings). Accept both.
        coerce_numbers_to_str=True,
        arbitrary_types_allowed=True,
    )

    # Drupal-side language of this document. Emitted by SearchMapper as
    # `_language`; aliased here because Pydantic v2 reserves leading-underscore
    # names. The `_language` attribute remains readable via a property below
    # so existing consumers (connections/tests, application_form tests) keep
    # working unchanged.
    language: Optional[str] = Field(default=None, alias="_language")

    # --- Project: identifiers ---
    # project_uuid / uuid were declared as ES `Keyword` in the legacy schema
    # and remained strings throughout the codebase. Keep them as strings here
    # to avoid churn in consumers that compare the UUID against plain-string
    # identifiers pulled from the Django database (e.g.
    # UserKeyValue.value stored as str).
    project_id: int
    project_uuid: str

    # --- Project: classification / address ---
    # required=True in the legacy ES schema, but Drupal may send empty values
    # for some fields during PRE_MARKETING/UNDER_PLANNING states, so these
    # are kept Optional to preserve backward compatibility with existing
    # ingestion. Missing values here do not raise; Pydantic lets consumers
    # (DRF serializers, PDFs) keep surfacing them as None.
    project_ownership_type: Optional[str] = None
    project_housing_company: Optional[str] = None
    project_holding_type: Optional[str] = None
    project_street_address: Optional[str] = None
    project_postal_code: Optional[str] = None
    project_city: Optional[str] = None
    project_contract_business_id: Optional[str] = None
    project_district: Optional[str] = None
    project_realty_id: Optional[str] = None
    project_construction_year: Optional[str] = None
    project_new_development_status: Optional[str] = None
    project_new_housing: Optional[bool] = None
    project_apartment_count: Optional[int] = None
    project_parkingplace_count: Optional[int] = None
    project_state_of_sale: Optional[str] = None
    project_property_number: Optional[str] = None

    project_has_elevator: Optional[bool] = None
    project_has_sauna: Optional[bool] = None
    project_construction_materials: List[str] = []
    project_roof_material: Optional[str] = None
    project_heating_options: List[str] = []
    project_energy_class: Optional[str] = None
    project_site_area: Optional[float] = None
    project_site_owner: Optional[str] = None
    project_site_renter: Optional[str] = None
    project_sanitation: Optional[str] = None
    project_zoning_info: Optional[str] = None
    project_zoning_status: Optional[str] = None

    project_building_type: Optional[str] = None
    project_description: Optional[str] = None
    project_accessibility: Optional[str] = None
    project_smoke_free: Optional[str] = None

    project_publication_start_time: Optional[datetime] = None
    project_publication_end_time: Optional[datetime] = None
    project_premarketing_start_time: Optional[datetime] = None
    project_premarketing_end_time: Optional[datetime] = None
    project_application_start_time: Optional[datetime] = None
    project_application_end_time: Optional[datetime] = None
    project_can_apply_afterwards: Optional[bool] = None
    project_material_choice_dl: Optional[datetime] = None
    project_shareholder_meeting_date: Optional[datetime] = None
    project_estimated_completion: Optional[str] = None
    project_estimated_completion_date: Optional[datetime] = None
    # project_completion_date was declared twice in the legacy ES schema
    # (Keyword then Date); the Date declaration won in Python. Keep as
    # datetime for continuity.
    project_completion_date: Optional[datetime] = None
    project_possession_transfer_date: Optional[datetime] = None
    project_shares_transferred_when: Optional[str] = None
    project_control_transferred_when: Optional[str] = None
    project_published: Optional[bool] = None
    project_archived: Optional[bool] = None

    project_attachment_urls: List[str] = []
    project_main_image_url: Optional[str] = None
    project_image_urls: List[str] = []
    project_virtual_presentation_url: Optional[str] = None
    project_url: Optional[str] = None
    project_use_complete_contract: Optional[bool] = None

    project_acc_salesperson: Optional[str] = None
    project_acc_financeofficer: Optional[str] = None
    project_project_manager: Optional[str] = None
    project_constructor: Optional[str] = None
    project_housing_manager: Optional[str] = None
    project_estate_agent: Optional[str] = None
    project_estate_agent_email: Optional[str] = None
    project_estate_agent_phone: Optional[str] = None

    project_coordinate_lat: Optional[float] = None
    project_coordinate_lon: Optional[float] = None

    project_barred_bank_account: Optional[str] = None
    project_regular_bank_account: Optional[str] = None
    project_payment_recipient: Optional[str] = None
    project_payment_recipient_final: Optional[str] = None

    # --- Apartment ---
    # uuid was ES `Keyword` and is still treated as a string everywhere in
    # the codebase; keep it as Optional[str]. It is absent from project-only
    # payloads returned by `/projects` endpoints.
    uuid: Optional[str] = None
    url: Optional[str] = None

    apartment_address: Optional[str] = None
    apartment_number: Optional[str] = None
    housing_shares: Optional[str] = None
    living_area: Optional[float] = None
    floor: Optional[int] = None
    floor_max: Optional[int] = None
    showing_times: List[datetime] = []
    apartment_structure: Optional[str] = None
    room_count: Optional[int] = None
    condition: Optional[str] = None
    kitchen_appliances: Optional[str] = None
    has_yard: Optional[bool] = None
    has_terrace: Optional[bool] = None
    has_balcony: Optional[bool] = None
    balcony_description: Optional[str] = None
    bathroom_appliances: Optional[str] = None
    storage_description: Optional[str] = None
    has_apartment_sauna: Optional[bool] = None
    apartment_holding_type: Optional[str] = None
    view_description: Optional[str] = None
    sales_price: Optional[int] = None
    debt_free_sales_price: Optional[int] = None
    loan_share: Optional[int] = None
    price_m2: Optional[int] = None
    housing_company_fee: Optional[int] = None
    financing_fee: Optional[int] = None
    financing_fee_m2: Optional[int] = None
    maintenance_fee: Optional[int] = None
    maintenance_fee_m2: Optional[int] = None
    water_fee: Optional[int] = None
    water_fee_explanation: Optional[str] = None
    parking_fee: Optional[int] = None
    parking_fee_explanation: Optional[str] = None
    other_fees: Optional[str] = None
    services_description: Optional[str] = None
    additional_information: Optional[str] = None
    application_url: Optional[str] = None
    floor_plan_image: Optional[str] = None
    image_urls: List[str] = []
    title: Optional[str] = None
    site_owner: Optional[str] = None
    services: List[str] = []
    apartment_state_of_sale: Optional[str] = None
    apartment_published: Optional[bool] = None
    publish_on_etuovi: Optional[bool] = None
    publish_on_oikotie: Optional[bool] = None
    stock_start_number: Optional[int] = None
    stock_end_number: Optional[int] = None

    right_of_occupancy_payment: Optional[int] = None
    right_of_occupancy_fee: Optional[int] = None
    right_of_occupancy_deposit: Optional[int] = None
    release_payment: Optional[int] = None

    # Synchronized by Drupal from ApartmentRevaluation model.
    field_index_adjusted_right_of_oc: Optional[int] = None
    field_alteration_work: Optional[int] = None

    project_contract_apartment_completion_selection_1: Optional[bool] = None
    project_contract_apartment_completion_selection_1_date: Optional[datetime] = None
    project_contract_apartment_completion_selection_2: Optional[bool] = None
    project_contract_apartment_completion_selection_2_start: Optional[datetime] = None
    project_contract_apartment_completion_selection_2_end: Optional[datetime] = None
    project_contract_apartment_completion_selection_3: Optional[bool] = None
    project_contract_apartment_completion_selection_3_date: Optional[datetime] = None
    project_contract_depositary: Optional[str] = None

    project_contract_estimated_handover_date_start: Optional[datetime] = None
    project_contract_estimated_handover_date_end: Optional[datetime] = None
    project_contract_customer_document_handover: Optional[str] = None
    project_contract_bill_of_sale_terms: Optional[str] = None
    project_contract_material_selection_date: Optional[datetime] = None
    project_contract_material_selection_description: Optional[str] = None
    project_contract_material_selection_later: Optional[bool] = None
    project_contract_other_terms: Optional[str] = None
    project_contract_usage_fees: Optional[str] = None
    project_contract_repository: Optional[str] = None
    project_contract_right_of_occupancy_payment_verification: Optional[str] = None
    project_contract_rs_bank: Optional[str] = None

    project_contract_collateral_type: Optional[str] = None
    project_contract_default_collateral: Optional[str] = None
    project_contract_construction_permit_requested: Optional[datetime] = None
    project_contract_article_of_association: Optional[str] = None
    project_contract_transfer_restriction: Optional[bool] = None
    project_customer_document_handover: Optional[str] = None
    project_documents_delivered: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_uuids_to_strings(cls, data: Any) -> Any:
        """
        Accept uuid.UUID instances for UUID-shaped fields.

        Test factories emit `factory.Faker("uuid4")` which produces
        `uuid.UUID` objects, while the real Drupal payload always sends
        strings. Keep the declared type `str` (legacy ES Keyword) by
        stringifying UUIDs here.
        """
        if not isinstance(data, dict):
            return data

        for field_name in ("uuid", "project_uuid"):
            value = data.get(field_name)
            if isinstance(value, UUID):
                data[field_name] = str(value)
        return data

    @model_validator(mode="before")
    @classmethod
    def _coerce_empty_strings_to_none(cls, data: Any) -> Any:
        """
        Replace '' with None for Optional typed (non-string) fields.

        SearchMapper::getScalar returns '' for missing scalar values in the
        Drupal response. Leaving '' in typed fields leads to ValidationError
        later and obscures the root cause (empty Drupal field). Emit a
        warning so data-quality issues are visible without breaking
        ingestion.
        """
        if not isinstance(data, dict):
            return data

        coerced_fields: List[str] = []
        for field_name in cls._empty_string_coercible_fields():
            if field_name not in data:
                continue
            if data[field_name] == "":
                data[field_name] = None
                coerced_fields.append(field_name)

        if coerced_fields:
            doc_uuid = data.get("uuid")
            project_uuid = data.get("project_uuid")
            logger.warning(
                "ApartmentDocument: coerced empty string to None for typed "
                "fields %s (uuid=%s, project_uuid=%s)",
                coerced_fields,
                doc_uuid,
                project_uuid,
            )

        return data

    @classmethod
    def _empty_string_coercible_fields(cls) -> List[str]:
        """
        Return the set of Optional non-string fields that should coerce ''
        to None. Computed lazily (once) from the Pydantic field definitions.
        """
        cached = cls.__dict__.get("_empty_coercible_cache")
        if cached is not None:
            return cached

        result: List[str] = []
        for name, field in cls.model_fields.items():
            annotation = field.annotation
            if not cls._annotation_is_optional_non_string(annotation):
                continue
            result.append(name)

        # Cache on the class to avoid repeated introspection on each validate.
        cls._empty_coercible_cache = result  # type: ignore[attr-defined]
        return result

    @staticmethod
    def _annotation_is_optional_non_string(annotation: Any) -> bool:
        """
        True if the annotation accepts None and does NOT accept str.

        Covers Optional[int], Optional[float], Optional[bool],
        Optional[datetime], Optional[UUID], Optional[List[...]], etc., and
        excludes Optional[str].
        """
        import types
        import typing
        from typing import get_args, get_origin

        origin = get_origin(annotation)
        if origin is typing.Union or origin is types.UnionType:
            args = get_args(annotation)
            if type(None) not in args:
                return False
            non_none = [a for a in args if a is not type(None)]
            # Exclude fields that accept str (e.g. Optional[str]).
            if any(a is str for a in non_none):
                return False
            # Require at least one typed alternative we want to coerce for.
            return bool(non_none)
        return False

    @property
    def _language(self) -> Optional[str]:
        """
        Backward-compatible access to the Drupal _language scalar.

        Pydantic v2 disallows leading-underscore model field names, so the
        field is declared as `language` with alias `_language` for input
        parsing; this property keeps attribute access (`document._language`)
        working for callers like connections/tests/utils.py.
        """
        return self.language

    def __getitem__(self, item: str) -> Any:
        """
        Backward-compatible subscript access.

        The legacy elasticsearch_dsl.Document accepted both dotted
        (`doc.field`) and subscript (`doc["field"]`) access. Some callers
        (notably api/serializers.py and nested DRF SerializerMethodField
        handlers) still rely on the latter, so expose it as an alias for
        attribute lookup and raise KeyError on unknown names to match the
        dict-like contract.
        """
        try:
            return getattr(self, item)
        except AttributeError as exc:
            raise KeyError(item) from exc

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        properties_to_print = []

        if self.project_uuid:
            properties_to_print += [
                "project_uuid",
                "project_housing_company",
            ]

        properties_to_print += [
            "uuid",
            "apartment_address",
        ]

        properties_str = ", ".join(
            f"{prop_name}='{getattr(self, prop_name)}'"
            for prop_name in properties_to_print
        )
        return f"ApartmentDocument({properties_str})"

    @property
    def current_right_of_occupancy_payment(self):
        """
        Determine the effective current right of occupancy payment by
        searching for updated values in local database.
        """
        return current_right_of_occupancy_payment(
            self.uuid, self.right_of_occupancy_payment
        )

    def reservation_right_of_occupancy_payment(self, reservation_id: int):
        return reservation_right_of_occupancy_payment(
            reservation_id, self.uuid, self.right_of_occupancy_payment
        )

    @property
    def project_contract_combined_terms(self) -> str:
        items = [
            self.project_contract_bill_of_sale_terms,
            self.project_contract_other_terms,
            self.project_contract_customer_document_handover,
        ]
        non_empty_items = [x for x in items if isinstance(x, str) and x]
        return "\n\n".join(non_empty_items)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to a plain dict.

        Preserves the elasticsearch-dsl API surface so existing callers that
        rely on `.to_dict()` keep working.
        """
        return self.model_dump(mode="json")
