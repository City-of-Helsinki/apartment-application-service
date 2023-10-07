import logging
import pprint
from contextlib import contextmanager

from .logger import LOG, log_context
from .nin_utils import redact_nin_values
from .object_store import get_object_store

_object_store = get_object_store()

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


@contextmanager
def log_context_from(instance):
    model = type(instance)
    asko_id = _object_store.get_asko_id(instance)
    with log_context(model=model, row={"id": asko_id}) as log:
        yield log
