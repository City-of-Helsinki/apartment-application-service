import logging
from elasticsearch_dsl import Search
from connections.utils import create_elastic_connection

_logger = logging.getLogger(__name__)
create_elastic_connection()


def fetch_sold_apartments():
    s_obj = (
        Search().exclude("match", _language="en").query(project_state_of_sale="SOLD")
    )
    s_obj.execute()
    scan = s_obj.scan()
    items = []

    for hit in scan:
        items.append(hit.id)
