import logging

from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property

LOG = logging.getLogger(__name__)


class LargeTablePaginator(Paginator):
    """
    Paginator that uses PostgreSQL `reltuples` for queryset size.

    The reltuples values is just an estimate, but it's much faster than
    the COUNT(*) which is used by the default paginator. Therefore this
    should work better for tables containing millions of rows.

    See https://wiki.postgresql.org/wiki/Count_estimate for details.
    """

    @cached_property
    def count(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT reltuples::bigint FROM pg_class WHERE relname = %s",
                [self.object_list.query.model._meta.db_table],
            )
            estimate = cursor.fetchone()[0]
            if estimate == -1:
                # If the table has not yet been analyzed/vacuumed,
                # reltuples will return -1.  In this case we fall back to
                # the default paginator.
                LOG.warning(
                    "Can't estimate count of table %s, using COUNT(*) instead",
                    self.object_list.query.model._meta.db_table,
                )
                return super().count
            return estimate
