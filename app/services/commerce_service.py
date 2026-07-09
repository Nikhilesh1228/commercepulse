from datetime import UTC, datetime
from typing import Any, cast

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters import cache, document_store, events, search
from app.models.commerce import (
    GroupBuy,
    GroupBuyMember,
    GroupBuyStatus,
    Order,
    PriceWatch,
    Product,
)
from app.schemas.commerce import GroupBuyCreate, OrderCreate, PriceWatchCreate, ProductCreate


def get_product(db: Session, product_id: str) -> Product:
    product = db.get(Product, product_id)
    if product is None or not product.active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


def create_product(db: Session, payload: ProductCreate, actor_id: str) -> Product:
    if db.scalar(select(Product).where(Product.sku == payload.sku)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")
    product = Product(**payload.model_dump(mode="json"))
    db.add(product)
    db.flush()
    events.enqueue(
        db,
        topic="catalog.product.created",
        event_key=product.id,
        payload={"product_id": product.id, "sku": product.sku, "actor_id": actor_id},
    )
    db.commit()
    db.refresh(product)
    search.index_product(product)
    cache.delete_pattern("commercepulse:search:*")
    events.publish_best_effort(db)
    return product


def search_products(db: Session, query: str | None, limit: int = 20) -> list[Product]:
    normalized = (query or "").strip().lower()
    cache_key = f"commercepulse:search:{normalized}:{limit}"
    cached = cache.get_json(cache_key)
    if isinstance(cached, list):
        cached_products: list[Product] = []
        for product_id in cached:
            cached_product = db.get(Product, str(product_id))
            if cached_product is not None and cached_product.active:
                cached_products.append(cached_product)
        return cached_products

    if normalized:
        ids = search.search_product_ids(normalized, limit)
        if ids is not None:
            by_id = {
                item.id: item for item in db.scalars(select(Product).where(Product.id.in_(ids)))
            }
            products = [by_id[item_id] for item_id in ids if item_id in by_id]
        else:
            pattern = f"%{normalized}%"
            products = list(
                db.scalars(
                    select(Product)
                    .where(
                        Product.active.is_(True),
                        or_(
                            Product.name.ilike(pattern),
                            Product.description.ilike(pattern),
                            Product.category.ilike(pattern),
                            Product.merchant.ilike(pattern),
                        ),
                    )
                    .order_by(Product.updated_at.desc())
                    .limit(limit)
                )
            )
    else:
        products = list(
            db.scalars(
                select(Product)
                .where(Product.active.is_(True))
                .order_by(Product.updated_at.desc())
                .limit(limit)
            )
        )
    cache.set_json(cache_key, [product.id for product in products], ttl_seconds=45)
    return products


def resolve_product_url(db: Session, product_url: str) -> Product:
    product = db.scalar(
        select(Product).where(Product.product_url == product_url, Product.active.is_(True))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product URL not indexed")
    return product


def update_price(
    db: Session,
    *,
    product_id: str,
    new_price_cents: int,
    expected_version: int,
    actor_id: str,
) -> Product:
    product = get_product(db, product_id)
    old_price = product.price_cents
    result = cast(
        CursorResult[Any],
        db.execute(
            update(Product)
            .where(Product.id == product_id, Product.version == expected_version)
            .values(
                price_cents=new_price_cents,
                version=expected_version + 1,
                updated_at=datetime.now(UTC),
            )
        ),
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product changed; reload before updating the price",
        )
    events.enqueue(
        db,
        topic="catalog.price.changed",
        event_key=product_id,
        payload={
            "product_id": product_id,
            "old_price_cents": old_price,
            "new_price_cents": new_price_cents,
            "actor_id": actor_id,
        },
    )
    db.commit()
    updated_product = get_product(db, product_id)
    search.index_product(updated_product)
    document_store.record_price_snapshot(
        product_id=product_id,
        old_price_cents=old_price,
        new_price_cents=new_price_cents,
        changed_by=actor_id,
    )
    cache.delete_pattern("commercepulse:search:*")
    events.publish_best_effort(db)
    return updated_product


def create_price_watch(db: Session, payload: PriceWatchCreate, user_id: str) -> PriceWatch:
    get_product(db, payload.product_id)
    watch = db.scalar(
        select(PriceWatch).where(
            PriceWatch.user_id == user_id, PriceWatch.product_id == payload.product_id
        )
    )
    if watch:
        watch.target_price_cents = payload.target_price_cents
        watch.active = True
    else:
        watch = PriceWatch(user_id=user_id, **payload.model_dump())
        db.add(watch)
    events.enqueue(
        db,
        topic="watchlist.price.created",
        event_key=payload.product_id,
        payload={
            "user_id": user_id,
            "product_id": payload.product_id,
            "target_price_cents": payload.target_price_cents,
        },
    )
    db.commit()
    db.refresh(watch)
    events.publish_best_effort(db)
    return watch


def create_group_buy(db: Session, payload: GroupBuyCreate, user_id: str) -> GroupBuy:
    get_product(db, payload.product_id)
    expires_at = payload.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Expiry must be future"
        )
    campaign = GroupBuy(created_by=user_id, **payload.model_dump(exclude={"expires_at"}))
    campaign.expires_at = expires_at
    db.add(campaign)
    db.flush()
    db.add(GroupBuyMember(group_buy_id=campaign.id, user_id=user_id))
    campaign.member_count = 1
    events.enqueue(
        db,
        topic="groupbuy.created",
        event_key=campaign.id,
        payload={"group_buy_id": campaign.id, "product_id": campaign.product_id},
    )
    db.commit()
    db.refresh(campaign)
    events.publish_best_effort(db)
    return campaign


def get_group_buy(db: Session, campaign_id: str) -> GroupBuy:
    campaign = db.get(GroupBuy, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group buy not found")
    return campaign


def join_group_buy(db: Session, campaign_id: str, user_id: str) -> GroupBuy:
    campaign = db.scalar(select(GroupBuy).where(GroupBuy.id == campaign_id).with_for_update())
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group buy not found")
    expires_at = campaign.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if campaign.status != GroupBuyStatus.OPEN.value or expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group buy is not open")
    db.add(GroupBuyMember(group_buy_id=campaign.id, user_id=user_id))
    campaign.member_count += 1
    if campaign.member_count >= campaign.target_members:
        campaign.status = GroupBuyStatus.UNLOCKED.value
    events.enqueue(
        db,
        topic="groupbuy.member.joined",
        event_key=campaign.id,
        payload={
            "group_buy_id": campaign.id,
            "user_id": user_id,
            "member_count": campaign.member_count,
            "status": campaign.status,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already joined") from exc
    db.refresh(campaign)
    events.publish_best_effort(db)
    return campaign


def list_group_buys(db: Session, limit: int = 20) -> list[GroupBuy]:
    return list(db.scalars(select(GroupBuy).order_by(GroupBuy.created_at.desc()).limit(limit)))


def create_order(db: Session, payload: OrderCreate, user_id: str) -> Order:
    quantities: dict[str, int] = {}
    for item in payload.items:
        quantities[item.product_id] = quantities.get(item.product_id, 0) + item.quantity
    products = list(db.scalars(select(Product).where(Product.id.in_(quantities)).with_for_update()))
    if len(products) != len(quantities):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="One or more products not found"
        )

    discount = 0
    if payload.group_buy_id:
        campaign = get_group_buy(db, payload.group_buy_id)
        if campaign.status != GroupBuyStatus.UNLOCKED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Group buy not unlocked"
            )
        discount = campaign.discount_percent

    currencies = {product.currency for product in products}
    if len(currencies) != 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Mixed currencies"
        )
    snapshots: list[dict[str, object]] = []
    total = 0
    for product in products:
        quantity = quantities[product.id]
        if product.inventory_count < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Insufficient inventory for {product.sku}",
            )
        unit_price = product.price_cents * (100 - discount) // 100
        product.inventory_count -= quantity
        total += unit_price * quantity
        snapshots.append(
            {
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name,
                "quantity": quantity,
                "unit_price_cents": unit_price,
            }
        )
    order = Order(
        user_id=user_id,
        group_buy_id=payload.group_buy_id,
        items=snapshots,
        total_cents=total,
        currency=next(iter(currencies)),
    )
    db.add(order)
    db.flush()
    events.enqueue(
        db,
        topic="order.created",
        event_key=order.id,
        payload={"order_id": order.id, "user_id": user_id, "total_cents": total},
    )
    db.commit()
    db.refresh(order)
    events.publish_best_effort(db)
    return order


def count_price_watches(db: Session, product_id: str) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(PriceWatch)
            .where(PriceWatch.product_id == product_id, PriceWatch.active.is_(True))
        )
        or 0
    )
