from django.apps import AppConfig

from connections.utils import create_elastic_connection


class ConnectionsConfig(AppConfig):
    name = "connections"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        create_elastic_connection()
