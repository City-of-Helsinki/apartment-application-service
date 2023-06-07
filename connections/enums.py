from enum import Enum


class Currency(Enum):
    EUR = "EUR"


class Unit(Enum):
    EUR_KK = "EUR/kk"
    M2 = "m2"


class ApartmentStateOfSale(str, Enum):
    FOR_SALE = "FOR_SALE"
    OPEN_FOR_APPLICATIONS = "OPEN_FOR_APPLICATIONS"
    FREE_FOR_RESERVATIONS = "FREE_FOR_RESERVATIONS"
    RESERVED = "RESERVED"
    RESERVED_HASO = "RESERVED_HASO"
    SOLD = "SOLD"


class ProjectStateOfSale(str, Enum):
    PRE_MARKETING = "PRE_MARKETING"
    FOR_SALE = "FOR_SALE"
    PROCESSING = "PROCESSING"
    READY = "READY"
