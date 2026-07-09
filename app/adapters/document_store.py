from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import get_settings


def record_price_snapshot(
    *, product_id: str, old_price_cents: int, new_price_cents: int, changed_by: str
) -> None:
    url = get_settings().mongodb_url
    if not url:
        return
    with suppress(PyMongoError):
        client: MongoClient[dict[str, Any]] = MongoClient(url, serverSelectionTimeoutMS=300)
        client.commercepulse.price_history.insert_one(
            {
                "product_id": product_id,
                "old_price_cents": old_price_cents,
                "new_price_cents": new_price_cents,
                "changed_by": changed_by,
                "changed_at": datetime.now(UTC),
            }
        )
        client.close()
