from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProductCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=80, pattern=r"^[A-Z0-9][A-Z0-9_-]+$")
    name: str = Field(min_length=2, max_length=180)
    description: str = Field(min_length=5, max_length=4000)
    category: str = Field(min_length=2, max_length=100)
    merchant: str = Field(min_length=2, max_length=120)
    product_url: HttpUrl
    price_cents: int = Field(gt=0)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    inventory_count: int = Field(default=0, ge=0)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    active: bool
    created_at: datetime
    updated_at: datetime


class PriceUpdate(BaseModel):
    price_cents: int = Field(gt=0)
    expected_version: int = Field(ge=1)


class PriceWatchCreate(BaseModel):
    product_id: str
    target_price_cents: int = Field(gt=0)


class PriceWatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    product_id: str
    target_price_cents: int
    active: bool
    created_at: datetime


class GroupBuyCreate(BaseModel):
    product_id: str
    target_members: int = Field(ge=2, le=500)
    discount_percent: int = Field(ge=1, le=80)
    expires_at: datetime


class GroupBuyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    created_by: str
    target_members: int
    discount_percent: int
    member_count: int
    status: str
    expires_at: datetime
    created_at: datetime


class OrderItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=100)


class OrderCreate(BaseModel):
    items: list[OrderItemRequest] = Field(min_length=1, max_length=50)
    group_buy_id: str | None = None


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    group_buy_id: str | None
    items: list[dict[str, object]]
    total_cents: int
    currency: str
    status: str
    created_at: datetime
