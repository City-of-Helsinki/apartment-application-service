from enum import Enum

from application_form.enums import ApartmentReservationState


class IdentifierSchemaType(Enum):
    ATT_PROJECT_ES = "att_pro_es"


class OwnershipType(Enum):
    HASO = "haso"
    HITAS = "hitas"
    HALF_HITAS = "half_hitas"


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
    def get_from_winner_reservation_state(
        cls, reservation_state: ApartmentReservationState
    ):
        try:
            return {
                ApartmentReservationState.RESERVED: cls.RESERVED,
                ApartmentReservationState.OFFERED: cls.OFFERED,
                ApartmentReservationState.OFFER_ACCEPTED: cls.OFFER_ACCEPTED,
                ApartmentReservationState.ACCEPTED_BY_MUNICIPALITY: cls.ACCEPTED_BY_MUNICIPALITY,  # noqa: E501
                ApartmentReservationState.SOLD: cls.SOLD,
                ApartmentReservationState.REVIEW: cls.REVIEW,
            }[reservation_state]
        except IndexError:
            raise ValueError(f"Invalid reservation state {reservation_state}")
