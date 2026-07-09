from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.security import Principal, get_current_principal
from app.db.session import get_db
from app.schemas.commerce import PriceWatchCreate, PriceWatchRead, ProductRead
from app.services import commerce_service

router = APIRouter(prefix="/catalog", tags=["catalog-extension"])


@router.get("/resolve", response_model=ProductRead)
def resolve_url(
    url: Annotated[str, Query(min_length=8, max_length=1000)],
    db: Annotated[Session, Depends(get_db)],
) -> ProductRead:
    return ProductRead.model_validate(commerce_service.resolve_product_url(db, url))


@router.get("/search", response_model=list[ProductRead])
def search_products(
    db: Annotated[Session, Depends(get_db)],
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ProductRead]:
    return [
        ProductRead.model_validate(product)
        for product in commerce_service.search_products(db, q, limit)
    ]


@router.post("/watchlist", response_model=PriceWatchRead, status_code=status.HTTP_201_CREATED)
def create_price_watch(
    payload: PriceWatchCreate,
    db: Annotated[Session, Depends(get_db)],
    principal: Annotated[Principal, Depends(get_current_principal)],
) -> PriceWatchRead:
    return PriceWatchRead.model_validate(
        commerce_service.create_price_watch(db, payload, principal.user_id)
    )
