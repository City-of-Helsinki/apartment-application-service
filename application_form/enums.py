from enum import Enum


class ApartmentReservationState(Enum):
    SUBMITTED = "submitted"
    RESERVED = "reserved"
    OFFERED = "offered"
    CANCELED = "canceled"
    REVIEW = "review"


class ApplicationType(Enum):
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"
    HASO = "haso"


class ApartmentQueueChangeEventType(Enum):
    ADDED = "added"
    REMOVED = "removed"
