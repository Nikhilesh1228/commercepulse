from datetime import UTC, datetime, timedelta

from tests.conftest import graphql


def create_group_buy(client, headers, product_id: str, target: int = 2):
    expires = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    response = graphql(
        client,
        f'mutation {{ createGroupBuy(productId: "{product_id}", targetMembers: {target}, '
        f'discountPercent: 15, expiresAt: "{expires}") '
        "{ id status memberCount targetMembers } }",
        headers,
    )
    assert "errors" not in response.json()
    return response.json()["data"]["createGroupBuy"]


def test_group_buy_unlocks_at_collective_threshold(
    client, shopper_headers, second_shopper_headers, created_product
):
    campaign = create_group_buy(client, shopper_headers, created_product["id"])
    assert campaign["memberCount"] == 1
    response = graphql(
        client,
        f'mutation {{ joinGroupBuy(groupBuyId: "{campaign["id"]}") {{ id status memberCount }} }}',
        second_shopper_headers,
    )
    assert response.json()["data"]["joinGroupBuy"]["status"] == "unlocked"
    assert response.json()["data"]["joinGroupBuy"]["memberCount"] == 2


def test_duplicate_group_buy_join_is_rejected(
    client, shopper_headers, second_shopper_headers, created_product
):
    campaign = create_group_buy(client, shopper_headers, created_product["id"], target=3)
    mutation = f'mutation {{ joinGroupBuy(groupBuyId: "{campaign["id"]}") {{ id memberCount }} }}'
    assert "errors" not in graphql(client, mutation, second_shopper_headers).json()
    assert "errors" in graphql(client, mutation, second_shopper_headers).json()


def test_order_applies_unlocked_group_discount(
    client, shopper_headers, second_shopper_headers, created_product
):
    campaign = create_group_buy(client, shopper_headers, created_product["id"])
    graphql(
        client,
        f'mutation {{ joinGroupBuy(groupBuyId: "{campaign["id"]}") {{ id }} }}',
        second_shopper_headers,
    )
    order = graphql(
        client,
        'mutation { createOrder(items: [{ productId: "'
        f'{created_product["id"]}", quantity: 2 }}], groupBuyId: "{campaign["id"]}") '
        "{ id totalCents currency status } }",
        shopper_headers,
    )
    payload = order.json()["data"]["createOrder"]
    assert payload["totalCents"] == (1599900 * 85 // 100) * 2
    assert payload["status"] == "pending"
