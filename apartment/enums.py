from enum import Enum

from application_form.enums import ApartmentReservationState


class IdentifierSchemaType(Enum):
    ATT_PROJECT_ES = "att_pro_es"


class OwnershipType(Enum):
    HASO = "haso"
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"


class ApartmentState(Enum):
    FREE = "free"
    RESERVED = "reserved"
    RESERVATION_AGREEMENT = "reservation_agreement"
    OFFERED = "offered"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_EXPIRED = "offer_expired"
    ACCEPTED_BY_MUNICIPALITY = "accepted_by_municipality"
    SOLD = "sold"
    REVIEW = "review"

    @classmethod
    def get_from_reserved_reservation_state(
        cls, reservation_state: ApartmentReservationState
    ):
        try:
            return {
                ApartmentReservationState.RESERVED: cls.RESERVED,
                ApartmentReservationState.RESERVATION_AGREEMENT: cls.RESERVATION_AGREEMENT,  # noqa: E501
                ApartmentReservationState.OFFERED: cls.OFFERED,
                ApartmentReservationState.OFFER_ACCEPTED: cls.OFFER_ACCEPTED,
                ApartmentReservationState.OFFER_EXPIRED: cls.OFFER_EXPIRED,
                ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY: cls.ACCEPTED_BY_MUNICIPALITY,  # noqa: E501
                ApartmentReservationState.SOLD: cls.SOLD,
                ApartmentReservationState.REVIEW: cls.REVIEW,
            }[reservation_state]
        except KeyError:
            raise ValueError(f"Invalid reserved reservation state {reservation_state}")
