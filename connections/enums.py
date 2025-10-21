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


class EtuoviEnergyClass(Enum):
    """
    Allowed energy classes for Etuovi
    """

    A = "A"
    A2007 = "A2007"
    B = "B"
    B2007 = "B2007"
    C = "C"
    C2007 = "C2007"
    D = "D"
    D2007 = "D2007"
    E = "E"
    E2007 = "E2007"
    F = "F"
    F2007 = "F2007"
    G = "G"
    G2007 = "G2007"
    H = "H"
