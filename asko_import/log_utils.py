import logging
import pprint

from .logger import LOG
from .nin_utils import redact_nin_values

# Whether to log National Identification Number values.
#
# This is a security risk, so it should be False in production.  It can
# be set to True in development environments to help developing the AsKo
# importer; for creating workarounds or fixes for bad data.
ALLOW_LOGGING_NIN_VALUES = False


def log_debug_nin_data(message: str, *args: object) -> None:
    if ALLOW_LOGGING_NIN_VALUES:
        log_debug_data(message, *args)


def log_debug_data(message: str, *args: object) -> None:
    log_pretty_data(logging.DEBUG, message, *args)


def log_pretty_data(level: int, message: str, *args: object) -> None:
    if LOG.isEnabledFor(level):
        if not ALLOW_LOGGING_NIN_VALUES:
            args = redact_nin_values(args)
        pretty_args = tuple(pprint.pformat(x) for x in args)
        LOG.log(level, message, *pretty_args)
