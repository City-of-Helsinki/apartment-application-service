from pytest import mark

from audit_log.models import AuditLog
from audit_log.paginators import LargeTablePaginator


@mark.django_db
def test_large_table_paginator_count_without_data():
    qs = AuditLog.objects.all().order_by("created_at")

    paginator = LargeTablePaginator(qs, per_page=1)

    # Paginator's count is just an estimate but it should be >= 0
    assert paginator.count >= 0


@mark.django_db
def test_large_table_paginator_count_with_data():
    AuditLog.objects.bulk_create(
        [AuditLog(message={"test": "test"}) for _ in range(1000)]
    )
    qs = AuditLog.objects.all().order_by("created_at")

    paginator = LargeTablePaginator(qs, per_page=1)

    # Paginator's count is just an estimate but it should be >= 0
    assert paginator.count >= 0
