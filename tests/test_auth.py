"""Auth tests — AUTH_USERS parsing, login flow, JWT issuance + validation."""
from importlib import reload

from fastapi.testclient import TestClient


def _client() -> TestClient:
    from app.main import app
    return TestClient(app)


def test_parse_auth_users_handles_whitespace_and_trailing_comma(monkeypatch):
    monkeypatch.setenv(
        "AUTH_USERS",
        "alice@vin.com:pw1, bob@vin.com:pw2  ,  charlie@vin.com:pw3,",
    )
    from app import auth as auth_mod
    reload(auth_mod)
    assert auth_mod._USER_DB == {
        "alice@vin.com": "pw1",
        "bob@vin.com": "pw2",
        "charlie@vin.com": "pw3",
    }


def test_login_returns_bearer_token_on_success(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "alice@vin.com:correcthorse")
    from app import auth as auth_mod
    reload(auth_mod)
    from app import main
    reload(main)
    client = TestClient(main.app)

    resp = client.post("/v1/auth/login", data={"username": "alice@vin.com", "password": "correcthorse"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["expires_in"] > 0


def test_login_rejects_wrong_password(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "alice@vin.com:correcthorse")
    from app import auth as auth_mod
    reload(auth_mod)
    from app import main
    reload(main)
    client = TestClient(main.app)

    resp = client.post("/v1/auth/login", data={"username": "alice@vin.com", "password": "WRONG"})
    assert resp.status_code == 401


def test_login_rejects_unknown_email(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "alice@vin.com:correcthorse")
    from app import auth as auth_mod
    reload(auth_mod)
    from app import main
    reload(main)
    client = TestClient(main.app)

    resp = client.post("/v1/auth/login", data={"username": "mallory@evil.com", "password": "anything"})
    assert resp.status_code == 401


def test_me_endpoint_requires_token(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "alice@vin.com:correcthorse")
    from app import auth as auth_mod
    reload(auth_mod)
    from app import main
    reload(main)
    client = TestClient(main.app)

    # Without token → 401
    resp = client.get("/v1/auth/me")
    assert resp.status_code == 401

    # With valid token → 200 + matching sub
    login = client.post("/v1/auth/login", data={"username": "alice@vin.com", "password": "correcthorse"})
    token = login.json()["access_token"]
    resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"email": "alice@vin.com"}


def test_login_email_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("AUTH_USERS", "alice@vin.com:correcthorse")
    from app import auth as auth_mod
    reload(auth_mod)
    from app import main
    reload(main)
    client = TestClient(main.app)

    resp = client.post("/v1/auth/login", data={"username": "Alice@VIN.com", "password": "correcthorse"})
    assert resp.status_code == 200
