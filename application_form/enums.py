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
    # The following ones are set automatically and cannot be chosen by users manually
    OTHER_APARTMENT_OFFERED = "other_apartment_offered"  # Toinen huoneisto tarjottu
    LOWER_PRIORITY = "lower_priority"  # Alemman prioriteetin
    OFFER_REJECTED = "offer_rejected"  # Tarjous hylätty


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


class ApplicationArrivalMethod(Enum):
    ELECTRONICAL_SYSTEM = "electronical_system"
    EMAIL = "email"
    POST = "post"
    DELIVERED = "delivered"
    PHONE = "phone"
