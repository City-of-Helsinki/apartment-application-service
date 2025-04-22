# apartment/elastic/utils.py
import functools

from elasticsearch_dsl import connections


@functools.lru_cache(maxsize=1)
def get_es_mapping(index_name="asuntotuotanto_apartment"):
    client = connections.get_connection()
    return client.indices.get_mapping(index=index_name)


def resolve_es_field(field_name: str, index_name="asuntotuotanto_apartment") -> str:
    mapping = get_es_mapping(index_name)
    props = mapping[index_name]["mappings"]["properties"]

    field_info = props.get(field_name)
    if not field_info:
        raise ValueError(f"Field '{field_name}' not found in mapping.")

    if field_info["type"] == "keyword":
        return field_name

    if (
        field_info["type"] == "text"
        and "fields" in field_info
        and "keyword" in field_info["fields"]
    ):
        return f"{field_name}.keyword"

    raise ValueError(
        f"Field '{field_name}' is not queryable (missing .keyword fallback)"
    )
