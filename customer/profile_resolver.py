from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from application_form.models import ApartmentReservation, Applicant, Application
    from customer.models import Customer
    from users.models import Profile


_MISSING_STRING_SENTINELS = {"", "-", "—", "–"}


@dataclass(frozen=True)
class ResolvedProfileData:
    """Resolved profile data for read-time API/PDF rendering."""

    id: Any
    first_name: str
    last_name: str
    email: str
    phone_number: str
    street_address: str
    city: str
    postal_code: str
    contact_language: str
    date_of_birth: date | None
    national_identification_number: str

    @property
    def full_name(self) -> str:
        """Return full name with normalized spacing."""
        return " ".join([part for part in [self.first_name, self.last_name] if part])


def _is_missing_string(value: Any) -> bool:
    """Return whether a string-like value should be treated as missing."""
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    return value.strip() in _MISSING_STRING_SENTINELS


def _normalize_string(value: Any) -> str:
    """Normalize string-like value to a clean string or empty string."""
    if _is_missing_string(value):
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _pick_profile_value(
    *,
    profile_value: Any,
    linked_applicant_value: Any,
    latest_applicant_value: Any,
    allow_latest_fallback: bool,
    default: Any,
    treat_as_string: bool,
) -> Any:
    """Pick value using profile -> linked applicant -> latest applicant priority."""
    if treat_as_string:
        profile_normalized = _normalize_string(profile_value)
        if profile_normalized:
            return profile_normalized

        linked_normalized = _normalize_string(linked_applicant_value)
        if linked_normalized:
            return linked_normalized

        if allow_latest_fallback:
            latest_normalized = _normalize_string(latest_applicant_value)
            if latest_normalized:
                return latest_normalized

        return default

    if profile_value is not None:
        return profile_value
    if linked_applicant_value is not None:
        return linked_applicant_value
    if allow_latest_fallback and latest_applicant_value is not None:
        return latest_applicant_value
    return default


def _get_applicants_by_role(
    application: Application | None,
) -> dict[bool, Applicant | None]:
    """Return first applicant per role (primary/secondary) from application."""
    result: dict[bool, Applicant | None] = {True: None, False: None}
    if application is None:
        return result

    for applicant in application.applicants.order_by("id"):
        is_primary = bool(applicant.is_primary_applicant)
        if result[is_primary] is None:
            result[is_primary] = applicant

    return result


def _get_latest_application_for_customer(customer: Customer) -> Application | None:
    """Return latest application for the given customer."""
    from application_form.models import Application

    return (
        Application.objects.filter(customer_id=customer.id)
        .prefetch_related("applicants")
        .order_by("-created_at", "-id")
        .first()
    )


def _resolve_profile_data(
    *,
    profile: Profile | None,
    linked_applicant: Applicant | None,
    latest_applicant: Applicant | None,
    allow_latest_fallback: bool,
) -> ResolvedProfileData | None:
    """Resolve one profile with application-based fallback values."""
    if profile is None:
        return None

    return ResolvedProfileData(
        id=profile.id,
        first_name=_pick_profile_value(
            profile_value=profile.first_name,
            linked_applicant_value=getattr(linked_applicant, "first_name", None),
            latest_applicant_value=getattr(latest_applicant, "first_name", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        last_name=_pick_profile_value(
            profile_value=profile.last_name,
            linked_applicant_value=getattr(linked_applicant, "last_name", None),
            latest_applicant_value=getattr(latest_applicant, "last_name", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        email=_pick_profile_value(
            profile_value=profile.email,
            linked_applicant_value=getattr(linked_applicant, "email", None),
            latest_applicant_value=getattr(latest_applicant, "email", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        phone_number=_pick_profile_value(
            profile_value=profile.phone_number,
            linked_applicant_value=getattr(linked_applicant, "phone_number", None),
            latest_applicant_value=getattr(latest_applicant, "phone_number", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        street_address=_pick_profile_value(
            profile_value=profile.street_address,
            linked_applicant_value=getattr(linked_applicant, "street_address", None),
            latest_applicant_value=getattr(latest_applicant, "street_address", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        city=_pick_profile_value(
            profile_value=profile.city,
            linked_applicant_value=getattr(linked_applicant, "city", None),
            latest_applicant_value=getattr(latest_applicant, "city", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        postal_code=_pick_profile_value(
            profile_value=profile.postal_code,
            linked_applicant_value=getattr(linked_applicant, "postal_code", None),
            latest_applicant_value=getattr(latest_applicant, "postal_code", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        contact_language=_pick_profile_value(
            profile_value=profile.contact_language,
            linked_applicant_value=getattr(linked_applicant, "contact_language", None),
            latest_applicant_value=getattr(latest_applicant, "contact_language", None),
            allow_latest_fallback=allow_latest_fallback,
            default="",
            treat_as_string=True,
        ),
        date_of_birth=_pick_profile_value(
            profile_value=profile.date_of_birth,
            linked_applicant_value=getattr(linked_applicant, "date_of_birth", None),
            latest_applicant_value=getattr(latest_applicant, "date_of_birth", None),
            allow_latest_fallback=allow_latest_fallback,
            default=None,
            treat_as_string=False,
        ),
        national_identification_number=_normalize_string(
            profile.national_identification_number
        ),
    )


def resolve_customer_profiles_for_reservation(
    reservation: ApartmentReservation,
) -> tuple[ResolvedProfileData | None, ResolvedProfileData | None]:
    """Resolve primary and secondary profiles for reservation context."""
    customer = reservation.customer
    linked_application = None
    if reservation.application_apartment is not None:
        linked_application = reservation.application_apartment.application

    linked_by_role = _get_applicants_by_role(linked_application)

    latest_by_role: dict[bool, Applicant | None] = {True: None, False: None}
    allow_latest_fallback = linked_application is None
    if allow_latest_fallback:
        latest_application = _get_latest_application_for_customer(customer)
        latest_by_role = _get_applicants_by_role(latest_application)

    primary = _resolve_profile_data(
        profile=customer.primary_profile,
        linked_applicant=linked_by_role[True],
        latest_applicant=latest_by_role[True],
        allow_latest_fallback=allow_latest_fallback,
    )
    secondary = _resolve_profile_data(
        profile=customer.secondary_profile,
        linked_applicant=linked_by_role[False],
        latest_applicant=latest_by_role[False],
        allow_latest_fallback=allow_latest_fallback,
    )
    return primary, secondary


def resolve_customer_profiles_for_customer(
    customer: Customer,
) -> tuple[ResolvedProfileData | None, ResolvedProfileData | None]:
    """Resolve primary and secondary profiles for customer detail context."""
    latest_application = _get_latest_application_for_customer(customer)
    latest_by_role = _get_applicants_by_role(latest_application)

    primary = _resolve_profile_data(
        profile=customer.primary_profile,
        linked_applicant=None,
        latest_applicant=latest_by_role[True],
        allow_latest_fallback=True,
    )
    secondary = _resolve_profile_data(
        profile=customer.secondary_profile,
        linked_applicant=None,
        latest_applicant=latest_by_role[False],
        allow_latest_fallback=True,
    )
    return primary, secondary
