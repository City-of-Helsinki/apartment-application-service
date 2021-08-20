from enum import Enum


class ApplicationState(Enum):
    SUBMITTED = "submitted"
    RESERVED = "reserved"
    REJECTED = "rejected"
    REVIEW = "review"


class ApplicationType(Enum):
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"
    HASO = "haso"
