from pytest import mark

from audit_log.models import AuditLog
from audit_log.paginators import LargeTablePaginator


@mark.django_db
def test_large_table_paginator_count():
    qs = AuditLog.objects.all()
    paginator = LargeTablePaginator(qs, per_page=1)
    assert paginator.count == qs.count()
