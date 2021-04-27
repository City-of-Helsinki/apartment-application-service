import logging
from django.core.management.base import BaseCommand

from connections.models import MappedApartment

_logger = logging.getLogger(__name__)


class Command(BaseCommand):  # pragma: no cover
    help = "Empty MappedApartment database table"

    def handle(self, *args, **options):
        try:
            MappedApartment.objects.all().delete()
            _logger.info("Succefully deleted mapped apartments from database")
        except Exception as e:
            _logger.error("Could not delete mapped apartments from database:", str(e))
            raise e
