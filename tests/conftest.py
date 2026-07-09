import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB = Path(__file__).parent / "commercepulse-test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["REDIS_URL"] = ""
os.environ["MONGODB_URL"] = ""
os.environ["ELASTICSEARCH_URL"] = ""
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = ""
os.environ["JWT_SECRET"] = "test-secret-with-sufficient-entropy"

from app.core.config import get_settings  # noqa: E402
from app.core.security import Principal, create_access_token, hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.commerce import User  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database() -> Generator[None, None, None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


def create_user(email: str, roles: list[str]) -> User:
    with SessionLocal() as db:
        user = User(
            email=email,
            display_name=email.split("@")[0],
            password_hash=hash_password("test-password-123"),
            roles=roles,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def token_headers(user: User) -> dict[str, str]:
    token = create_access_token(
        Principal(user_id=user.id, email=user.email, roles=user.roles), get_settings()
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seller_headers() -> dict[str, str]:
    return token_headers(create_user("seller@example.com", ["seller"]))


@pytest.fixture
def shopper_headers() -> dict[str, str]:
    return token_headers(create_user("shopper@example.com", ["shopper"]))


@pytest.fixture
def second_shopper_headers() -> dict[str, str]:
    return token_headers(create_user("shopper2@example.com", ["shopper"]))


@pytest.fixture
def product_input() -> dict[str, object]:
    return {
        "sku": "HEADPHONES_001",
        "name": "Adaptive Focus Headphones",
        "description": "Noise cancelling headphones with repairable modular parts",
        "category": "audio",
        "merchant": "Future Sound",
        "productUrl": "https://shop.example.com/products/headphones-001",
        "priceCents": 1599900,
        "currency": "INR",
        "inventoryCount": 20,
    }


def graphql(client: TestClient, query: str, headers: dict[str, str] | None = None):
    return client.post("/graphql", json={"query": query}, headers=headers or {})


@pytest.fixture
def created_product(client: TestClient, seller_headers, product_input) -> dict[str, object]:
    fields = ", ".join(
        f'{key}: "{value}"' if isinstance(value, str) else f"{key}: {value}"
        for key, value in product_input.items()
    )
    response = graphql(
        client,
        f"mutation {{ createProduct(input: {{ {fields} }}) {{ id sku name priceCents version }} }}",
        seller_headers,
    )
    assert response.status_code == 200
    assert "errors" not in response.json()
    return response.json()["data"]["createProduct"]
