from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.ratelimit import limiter
from app.security import create_token, decode_token, hash_password, verify_password
from tests.conftest import register

CREDS = {"email": "user@example.com", "password": "password123"}


def test_register_creates_user_and_normalizes_email(client: TestClient) -> None:
    res = client.post(
        "/api/auth/register", json={"email": " User@Example.COM ", "password": "password123"}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["email"] == "user@example.com"
    assert body["timezone"] == "Europe/Moscow"
    assert "password" not in body and "password_hash" not in body


def test_register_duplicate_email_is_409(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=CREDS).status_code == 201
    upper = {**CREDS, "email": CREDS["email"].upper()}
    assert client.post("/api/auth/register", json=upper).status_code == 409


def test_register_validation(client: TestClient) -> None:
    short = client.post("/api/auth/register", json={**CREDS, "password": "short"})
    assert short.status_code == 422
    bad_email = client.post("/api/auth/register", json={**CREDS, "email": "not-an-email"})
    assert bad_email.status_code == 422


def test_login_returns_access_token_and_httponly_refresh_cookie(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    res = client.post("/api/auth/login", json=CREDS)
    assert res.status_code == 200
    assert res.json()["token_type"] == "bearer"
    set_cookie = res.headers["set-cookie"].lower()
    assert "refresh_token=" in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "secure" not in set_cookie  # dev mode
    assert "path=/api/auth" in set_cookie


def test_login_errors_do_not_reveal_whether_email_exists(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    wrong_pw = client.post("/api/auth/login", json={**CREDS, "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={**CREDS, "email": "nobody@example.com"})
    assert wrong_pw.status_code == unknown.status_code == 401
    assert wrong_pw.json() == unknown.json()


def test_refresh_issues_new_access_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    client.post("/api/auth/login", json=CREDS)
    res = client.post("/api/auth/refresh")
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == CREDS["email"]


def test_refresh_without_cookie_is_401(client: TestClient) -> None:
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_rejects_access_token_in_cookie(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    login = client.post("/api/auth/login", json=CREDS)
    client.cookies.clear()
    client.cookies.set("refresh_token", login.json()["access_token"], path="/api/auth")
    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_clears_cookie(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    client.post("/api/auth/login", json=CREDS)
    res = client.post("/api/auth/logout")
    assert res.status_code == 204
    assert client.post("/api/auth/refresh").status_code == 401


def test_protected_endpoints_require_bearer_token(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_refresh_token_cannot_be_used_as_access_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    refresh_token = create_token(1, "refresh")
    res = client.get("/api/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert res.status_code == 401


def test_expired_access_token_is_rejected(client: TestClient) -> None:
    client.post("/api/auth/register", json=CREDS)
    old = datetime.now(UTC) - timedelta(hours=1)
    token = create_token(1, "access", now=old)
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_of_deleted_user_is_rejected(client: TestClient) -> None:
    token = create_token(999, "access")
    assert client.get("/api/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_auth_endpoints_are_rate_limited(client: TestClient) -> None:
    limiter.enabled = True
    limiter.reset()
    codes = [client.post("/api/auth/login", json=CREDS).status_code for _ in range(12)]
    assert codes[:10] == [401] * 10
    assert codes[10:] == [429, 429]


def test_me_get_and_patch(client: TestClient, user_a: dict[str, str]) -> None:
    res = client.patch(
        "/api/me", headers=user_a, json={"cf_handle": " tourist ", "timezone": "Asia/Tokyo"}
    )
    assert res.status_code == 200
    assert res.json()["cf_handle"] == "tourist"
    assert client.get("/api/me", headers=user_a).json()["timezone"] == "Asia/Tokyo"

    cleared = client.patch("/api/me", headers=user_a, json={"cf_handle": None})
    assert cleared.json()["cf_handle"] is None
    assert cleared.json()["timezone"] == "Asia/Tokyo"  # untouched fields stay


def test_me_patch_rejects_unknown_timezone(client: TestClient, user_a: dict[str, str]) -> None:
    res = client.patch("/api/me", headers=user_a, json={"timezone": "Mars/Olympus"})
    assert res.status_code == 422


def test_users_are_independent(client: TestClient) -> None:
    a = register(client, "a@example.com")
    b = register(client, "b@example.com")
    client.patch("/api/me", headers=a, json={"cf_handle": "alice"})
    assert client.get("/api/me", headers=b).json()["cf_handle"] is None


def test_password_hashing_and_tokens() -> None:
    hashed = hash_password("secret-password")
    assert hashed != "secret-password"
    assert verify_password("secret-password", hashed)
    assert not verify_password("other", hashed)
    assert not verify_password("anything", None)
    assert not verify_password("anything", "not-a-hash")
    assert decode_token(create_token(7, "access"), "access") == 7
    assert decode_token(create_token(7, "access"), "refresh") is None
    assert decode_token("junk", "access") is None
