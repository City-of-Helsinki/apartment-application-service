import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from elasticsearch import Elasticsearch

from audit_log.models import AuditLog

ES_STATUS_CREATED = "created"
LOGGER = logging.getLogger(__name__)


def send_audit_log_to_elastic_search():
    if not (
        settings.AUDIT_LOG_ELASTICSEARCH_HOST
        and settings.AUDIT_LOG_ELASTICSEARCH_PORT
        and settings.ELASTICSEARCH_APP_AUDIT_LOG_INDEX
        and settings.AUDIT_LOG_ELASTICSEARCH_USERNAME
        and settings.AUDIT_LOG_ELASTICSEARCH_PASSWORD
    ):
        LOGGER.warning(
            "Trying to send audit log to Elasticsearch without proper configuration,"
            "process skipped"
        )
        return
    es = Elasticsearch(
        [
            {
                "host": settings.AUDIT_LOG_ELASTICSEARCH_HOST,
                "port": settings.AUDIT_LOG_ELASTICSEARCH_PORT,
                "use_ssl": True,
            }
        ],
        http_auth=(
            settings.AUDIT_LOG_ELASTICSEARCH_USERNAME,
            settings.AUDIT_LOG_ELASTICSEARCH_PASSWORD,
        ),
    )
    entries = AuditLog.objects.filter(sent_at=None).order_by("created_at")

    for entry in entries:
        message_body = entry.message.copy()
        message_body["@timestamp"] = entry.message["audit_event"][
            "date_time_epoch"
        ]  # required by ES
        rs = es.index(
            index=settings.ELASTICSEARCH_APP_AUDIT_LOG_INDEX,
            id=entry.id,
            body=message_body,
            op_type="create",
        )
        if rs.get("result") == ES_STATUS_CREATED:
            entry.sent_at = timezone.now()
            entry.save()
    return entries.count()


def clear_audit_log_entries(days_to_keep=30):
    # Only remove entries older than `X` days
    sent_entries = AuditLog.objects.exclude(sent_at=None).filter(
        created_at__lte=(timezone.now() - timedelta(days=days_to_keep))
    )
    return sent_entries.delete()
