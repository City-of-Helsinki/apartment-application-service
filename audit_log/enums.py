from enum import Enum


class Operation(Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class Role(Enum):
    OWNER = "OWNER"
    SYSTEM = "SYSTEM"


class Status(Enum):
    SUCCESS = "SUCCESS"
    FORBIDDEN = "FORBIDDEN"
