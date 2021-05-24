from enum import Enum


class ApplicationState(Enum):
    SUBMITTED = "submitted"
    RESERVED = "reserved"


class ApplicationType(Enum):
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"
    HASO = "haso"
