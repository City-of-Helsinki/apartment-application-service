from django.conf import settings
from elasticsearch_dsl import connections


def create_elastic_connection():
    connections.create_connection(hosts=[settings.ELASTICSEARCH_URL])
