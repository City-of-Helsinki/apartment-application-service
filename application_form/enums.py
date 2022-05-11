from enum import Enum


class ApartmentReservationState(Enum):
    SUBMITTED = "submitted"
    RESERVED = "reserved"
    RESERVATION_AGREEMENT = "reservation_agreement"
    OFFERED = "offered"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_EXPIRED = "offer_expired"
    ACCEPTED_BY_MUNICIPALITY = "accepted_by_municipality"
    SOLD = "sold"
    CANCELED = "canceled"
    REVIEW = "review"


class ApartmentReservationCancellationReason(Enum):
    TERMINATED = "terminated"  # Irtisanottu
    CANCELED = "canceled"  # Varaus peruttu
    RESERVATION_AGREEMENT_CANCELED = (
        "reservation_agreement_canceled"  # Varaussopimus peruttu
    )
    TRANSFERRED = "transferred"  # Siirretty


class ApplicationType(Enum):
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"
    HASO = "haso"


class ApartmentQueueChangeEventType(Enum):
    ADDED = "added"
    REMOVED = "removed"


class OfferState(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
