def test_health_and_root(client):
    assert client.get("/").json()["service"] == "CommercePulse"
    assert client.get("/api/v1/health/live").status_code == 200
    assert client.get("/api/v1/health/ready").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_register_login_and_me(client):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "display_name": "New Shopper",
            "password": "a-strong-password",
        },
    )
    assert registration.status_code == 201
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).json()["email"] == "new@example.com"

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "new@example.com", "password": "a-strong-password"},
    )
    assert login.status_code == 200


def test_duplicate_registration_and_bad_login(client):
    payload = {
        "email": "duplicate@example.com",
        "display_name": "Duplicate",
        "password": "a-strong-password",
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    payload["password"] = "wrong-password"
    assert client.post("/api/v1/auth/login", json=payload).status_code == 401


def test_oidc_requires_configuration(client):
    assert client.get("/api/v1/auth/oidc/start", follow_redirects=False).status_code == 503
