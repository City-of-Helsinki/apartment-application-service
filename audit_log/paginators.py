from django.core.paginator import Paginator
from django.db import connection
from django.utils.functional import cached_property


class LargeTablePaginator(Paginator):
    """
    Paginator that uses PostgreSQL `reltuples` for queryset size. This is much faster
    than the naive count implemented by the default paginator, so it works better for
    tables containing millions of rows.
    """

    @cached_property
    def count(self):
        cursor = connection.cursor()
        cursor.execute(
            "SELECT reltuples FROM pg_class WHERE relname = %s",
            [self.object_list.query.model._meta.db_table],
        )
        return int(cursor.fetchone()[0])
