from django.apps import AppConfig

from connections.utils import create_elastic_connection


class ConnectionsConfig(AppConfig):
    name = "connections"

    def ready(self):
        create_elastic_connection()
