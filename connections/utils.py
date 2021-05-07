from decimal import Decimal
from django.conf import settings
from elasticsearch_dsl import connections


def create_elastic_connection() -> None:
    """
    Creates the ElasticSearch connection with the url provided in the settings.
    The ElasticSearch connection needs to be established before it can be accessed.
    """
    connections.create_connection(
        hosts=[settings.ELASTICSEARCH_URL], port=settings.ELASTICSEARCH_PORT
    )


def convert_price_from_cents_to_eur(price: int) -> Decimal:
    """
    Prices are saved as cents in ElasticSearch. Convert to EUR.
    """
    return Decimal(price / 100.0)
