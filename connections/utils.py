from decimal import Decimal
from django.conf import settings
from elasticsearch_dsl import connections


def create_elastic_connection() -> None:
    """
    Creates the ElasticSearch connection with the url provided in the settings.
    """
    connections.create_connection(hosts=[settings.ELASTICSEARCH_URL])


def convert_price_from_cents_to_eur(price: int) -> Decimal:
    """
    Prices are saved as cents in ElasticSearch. Convert to EUR.
    """
    return Decimal(price / 100.0)
