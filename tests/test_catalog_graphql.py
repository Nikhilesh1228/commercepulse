from tests.conftest import graphql


def test_seller_creates_and_public_searches_product(client, seller_headers, created_product):
    response = client.get("/api/v1/catalog/search", params={"q": "headphones"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == created_product["id"]

    graphql_response = graphql(
        client,
        '{ products(search: "audio") { sku name inventoryCount } }',
    )
    assert graphql_response.json()["data"]["products"][0]["sku"] == "HEADPHONES_001"


def test_shopper_cannot_create_product(client, shopper_headers, product_input):
    response = graphql(
        client,
        'mutation { createProduct(input: { sku: "X_1", name: "Blocked", '
        'description: "Not allowed product", category: "test", merchant: "Test", '
        'productUrl: "https://example.com/x", priceCents: 100 }) { id } }',
        shopper_headers,
    )
    assert response.status_code == 200
    assert "errors" in response.json()


def test_price_update_uses_optimistic_lock(client, seller_headers, created_product):
    product_id = created_product["id"]
    response = graphql(
        client,
        f'mutation {{ updatePrice(productId: "{product_id}", priceCents: 1499900, '
        "expectedVersion: 1) { id priceCents version } }",
        seller_headers,
    )
    assert response.json()["data"]["updatePrice"]["version"] == 2

    conflict = graphql(
        client,
        f'mutation {{ updatePrice(productId: "{product_id}", priceCents: 1399900, '
        "expectedVersion: 1) { id } }",
        seller_headers,
    )
    assert "errors" in conflict.json()


def test_extension_resolves_url_and_creates_watch(client, shopper_headers, created_product):
    url = "https://shop.example.com/products/headphones-001"
    resolved = client.get("/api/v1/catalog/resolve", params={"url": url})
    assert resolved.status_code == 200
    assert resolved.json()["id"] == created_product["id"]

    watch = client.post(
        "/api/v1/catalog/watchlist",
        headers=shopper_headers,
        json={"product_id": created_product["id"], "target_price_cents": 1299900},
    )
    assert watch.status_code == 201
    assert watch.json()["target_price_cents"] == 1299900
