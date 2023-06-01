import logging
import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand

_logger = logging.getLogger(__name__)


class Command(BaseCommand):  # pragma: no cover
    help = "Create folder from env vars for ftp data transfer files"

    def handle(self, *args, **options):
        path = settings.APARTMENT_DATA_TRANSFER_PATH
        access_rights = 0o777

        try:
            os.mkdir(path, access_rights)
        except FileExistsError:
            # directory already exists
            pass
        except OSError as e:
            _logger.error(f"Creation of the directory {path} failed", e)
            sys.exit(1)
        else:
            _logger.info(f"Successfully created the directory {path}")
