from datetime import datetime
from typing import Annotated

import strawberry
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from strawberry.fastapi import BaseContext, GraphQLRouter

from app.core.security import Principal, get_optional_principal
from app.db.session import get_db
from app.models.commerce import GroupBuy, Product
from app.schemas.commerce import GroupBuyCreate, OrderCreate, OrderItemRequest, ProductCreate
from app.services import commerce_service


@strawberry.type
class ProductType:
    id: str
    sku: str
    name: str
    description: str
    category: str
    merchant: str
    product_url: str
    price_cents: int
    currency: str
    inventory_count: int
    version: int


@strawberry.type
class GroupBuyType:
    id: str
    product_id: str
    target_members: int
    discount_percent: int
    member_count: int
    status: str
    expires_at: datetime


@strawberry.type
class OrderType:
    id: str
    user_id: str
    total_cents: int
    currency: str
    status: str


@strawberry.input
class ProductInput:
    sku: str
    name: str
    description: str
    category: str
    merchant: str
    product_url: str
    price_cents: int
    currency: str = "INR"
    inventory_count: int = 0


@strawberry.input
class OrderItemInput:
    product_id: str
    quantity: int


class Context(BaseContext):
    def __init__(self, db: Session, principal: Principal | None) -> None:
        self.db = db
        self.principal = principal


def get_context(
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal | None, Depends(get_optional_principal)],
) -> Context:
    return Context(db, principal)


def require_principal(info: strawberry.Info[Context, None], *roles: str) -> Principal:
    principal = info.context.principal
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    if roles and not set(roles).intersection(principal.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return principal


def product_type(product: Product) -> ProductType:
    return ProductType(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        category=product.category,
        merchant=product.merchant,
        product_url=product.product_url,
        price_cents=product.price_cents,
        currency=product.currency,
        inventory_count=product.inventory_count,
        version=product.version,
    )


def group_buy_type(campaign: GroupBuy) -> GroupBuyType:
    return GroupBuyType(
        id=campaign.id,
        product_id=campaign.product_id,
        target_members=campaign.target_members,
        discount_percent=campaign.discount_percent,
        member_count=campaign.member_count,
        status=campaign.status,
        expires_at=campaign.expires_at,
    )


@strawberry.type
class Query:
    @strawberry.field
    def products(
        self, info: strawberry.Info[Context, None], search: str | None = None, limit: int = 20
    ) -> list[ProductType]:
        return [
            product_type(product)
            for product in commerce_service.search_products(
                info.context.db, search, min(limit, 100)
            )
        ]

    @strawberry.field
    def group_buys(
        self, info: strawberry.Info[Context, None], limit: int = 20
    ) -> list[GroupBuyType]:
        return [
            group_buy_type(campaign)
            for campaign in commerce_service.list_group_buys(info.context.db, min(limit, 100))
        ]


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_product(
        self, info: strawberry.Info[Context, None], input: ProductInput
    ) -> ProductType:
        principal = require_principal(info, "seller", "admin")
        payload = ProductCreate(**input.__dict__)
        return product_type(
            commerce_service.create_product(info.context.db, payload, principal.user_id)
        )

    @strawberry.mutation
    def update_price(
        self,
        info: strawberry.Info[Context, None],
        product_id: str,
        price_cents: int,
        expected_version: int,
    ) -> ProductType:
        principal = require_principal(info, "seller", "admin")
        return product_type(
            commerce_service.update_price(
                info.context.db,
                product_id=product_id,
                new_price_cents=price_cents,
                expected_version=expected_version,
                actor_id=principal.user_id,
            )
        )

    @strawberry.mutation
    def create_group_buy(
        self,
        info: strawberry.Info[Context, None],
        product_id: str,
        target_members: int,
        discount_percent: int,
        expires_at: datetime,
    ) -> GroupBuyType:
        principal = require_principal(info)
        payload = GroupBuyCreate(
            product_id=product_id,
            target_members=target_members,
            discount_percent=discount_percent,
            expires_at=expires_at,
        )
        return group_buy_type(
            commerce_service.create_group_buy(info.context.db, payload, principal.user_id)
        )

    @strawberry.mutation
    def join_group_buy(
        self, info: strawberry.Info[Context, None], group_buy_id: str
    ) -> GroupBuyType:
        principal = require_principal(info)
        return group_buy_type(
            commerce_service.join_group_buy(info.context.db, group_buy_id, principal.user_id)
        )

    @strawberry.mutation
    def create_order(
        self,
        info: strawberry.Info[Context, None],
        items: list[OrderItemInput],
        group_buy_id: str | None = None,
    ) -> OrderType:
        principal = require_principal(info)
        payload = OrderCreate(
            items=[OrderItemRequest(**item.__dict__) for item in items],
            group_buy_id=group_buy_id,
        )
        order = commerce_service.create_order(info.context.db, payload, principal.user_id)
        return OrderType(
            id=order.id,
            user_id=order.user_id,
            total_cents=order.total_cents,
            currency=order.currency,
            status=order.status,
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
graphql_router = GraphQLRouter(schema, context_getter=get_context)
