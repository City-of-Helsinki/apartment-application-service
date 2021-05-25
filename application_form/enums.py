from enum import Enum


class ApplicationState(Enum):
    SUBMITTED = "submitted"
    RESERVED = "reserved"


class ApplicationType(Enum):
    HITAS = "hitas"
    PUOLIHITAS = "puolihitas"
    HASO = "haso"


# awaiting definition
class AttachmentType(Enum):
    PREGNANCY = "raskaustodistus"
    INCOME = "tulotodistus"


# awaiting definition
class FileFormat(Enum):
    PDF = "pdf"
    JPG = "jpg"
    BMP = "bmp"
