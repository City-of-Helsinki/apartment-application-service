from django.db import connection
from pytest import mark

from audit_log.models import AuditLog
from audit_log.paginators import LargeTablePaginator


@mark.django_db
def test_large_table_paginator_count():
    qs = AuditLog.objects.all()
    paginator = LargeTablePaginator(qs, per_page=1)

    # Starting from PSQL 14 reltypes will return -1 on a table that has not
    # yet been vacuumed
    if connection.cursor().connection.server_version >= 140000:
        assert paginator.count == -1
    else:
        assert paginator.count == qs.count()
