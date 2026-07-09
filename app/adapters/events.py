import json
from contextlib import suppress
from datetime import UTC, datetime

from kafka import KafkaProducer  # type: ignore[import-untyped]
from kafka.errors import KafkaError  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.commerce import OutboxEvent


def enqueue(db: Session, *, topic: str, event_key: str, payload: dict[str, object]) -> None:
    db.add(OutboxEvent(topic=topic, event_key=event_key, payload=payload))


def publish_pending(db: Session, limit: int = 50) -> int:
    servers = get_settings().kafka_bootstrap_servers
    if not servers:
        return 0
    events = list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.published_at.is_(None))
            .order_by(OutboxEvent.created_at)
            .limit(limit)
        )
    )
    if not events:
        return 0
    try:
        producer = KafkaProducer(
            bootstrap_servers=servers.split(","),
            value_serializer=lambda value: json.dumps(value, default=str).encode(),
            acks="all",
            retries=3,
        )
        for event in events:
            producer.send(event.topic, key=event.event_key.encode(), value=event.payload).get(
                timeout=3
            )
            event.published_at = datetime.now(UTC)
        producer.flush(timeout=3)
        producer.close(timeout=3)
        db.commit()
        return len(events)
    except KafkaError:
        db.rollback()
        return 0


def publish_best_effort(db: Session) -> None:
    with suppress(Exception):
        publish_pending(db)
