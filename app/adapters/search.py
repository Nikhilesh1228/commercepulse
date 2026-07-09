from contextlib import suppress
from typing import Any

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError

from app.core.config import get_settings
from app.models.commerce import Product

INDEX = "commercepulse-products-v1"


def _client() -> Elasticsearch | None:
    url = get_settings().elasticsearch_url
    return Elasticsearch(url, request_timeout=0.5) if url else None


def index_product(product: Product) -> None:
    client = _client()
    if client:
        document = {
            "sku": product.sku,
            "name": product.name,
            "description": product.description,
            "category": product.category,
            "merchant": product.merchant,
            "price_cents": product.price_cents,
            "active": product.active,
        }
        with suppress(ApiError, ElasticConnectionError):
            client.index(index=INDEX, id=product.id, document=document, refresh=False)


def search_product_ids(query: str, limit: int) -> list[str] | None:
    client = _client()
    if client is None:
        return None
    try:
        result: dict[str, Any] = client.search(
            index=INDEX,
            size=limit,
            query={
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": ["name^3", "category^2", "description", "merchant"],
                            "fuzziness": "AUTO",
                        }
                    },
                    "filter": [{"term": {"active": True}}],
                }
            },
        ).body
        return [str(hit["_id"]) for hit in result["hits"]["hits"]]
    except (ApiError, ElasticConnectionError, KeyError, TypeError):
        return None
