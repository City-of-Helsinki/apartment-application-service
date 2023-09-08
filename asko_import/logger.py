import logging
from contextlib import contextmanager
from typing import Dict, Optional, Type, TypedDict

from django.db import models

from asko_import.models import AsKoImportLogEntry

_RAW_LOG = logging.getLogger(__name__.rsplit(".", 1)[0])


class LoggingContext(TypedDict, total=False):
    model: Optional[Type[models.Model]]
    row: Optional[Dict[str, object]]


class LoggerAdapter(logging.LoggerAdapter):
    extra: LoggingContext

    def log(self, level, msg, *args, **kwargs):
        super().log(level, msg, *args, **kwargs)
        self.store_to_database(level, msg, args, kwargs)

    def store_to_database(self, level, msg, args, kwargs):
        AsKoImportLogEntry.store(
            level=level,
            message_template=msg,
            message=msg % args,
            model=self.extra.get("model"),
            asko_id=(self.extra.get("row") or {}).get("id"),
        )


LOG = LoggerAdapter(_RAW_LOG, {})


@contextmanager
def log_context(model=None, row=None):
    old_extra = LOG.extra
    LOG.extra = {"model": model, "row": row}
    try:
        yield LOG
    finally:
        LOG.extra = old_extra
