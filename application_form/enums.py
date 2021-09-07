from enum import Enum


class ApplicationState(Enum):
    SUBMITTED = "submitted"
    RESERVED = "reserved"
    CANCELED = "canceled"
    REVIEW = "review"


class ApplicationType(Enum):
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"
    HASO = "haso"


class ApartmentQueueChangeEventType(Enum):
    ADDED = "added"
    REMOVED = "removed"
