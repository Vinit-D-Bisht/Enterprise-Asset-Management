import pytest
from sqlalchemy import select

from app.models import LoginThrottleBucket, RefreshSession, Role


def test_protected_routes_require_authentication(client):
    response = client.get("/api/v1/assets")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_rejects_untrusted_origin(client):
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"email": "administrator@example.com", "password": "irrelevant"},
    )
    assert response.status_code == 403


def test_login_rejects_untrusted_browser_origin(client):
    response = client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://attacker.example"},
        json={"email": "administrator@example.com", "password": "irrelevant"},
    )
    assert response.status_code == 403


def test_login_refresh_rotation_and_reuse_revocation(client, users):
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "administrator@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    original_refresh = client.cookies.get("eamms_refresh")
    assert original_refresh
    assert "HttpOnly" in login.headers["set-cookie"]
    assert (
        client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
        ).status_code
        == 200
    )

    refreshed = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "http://localhost:3000"}
    )
    assert refreshed.status_code == 200
    replacement = client.cookies.get("eamms_refresh")
    assert replacement and replacement != original_refresh

    client.cookies.set("eamms_refresh", original_refresh)
    replay = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "http://localhost:3000"}
    )
    assert replay.status_code == 401
    client.cookies.set("eamms_refresh", replacement)
    after_replay = client.post(
        "/api/v1/auth/refresh", headers={"Origin": "http://localhost:3000"}
    )
    assert after_replay.status_code == 401


def test_logout_revokes_refresh_session_and_clears_cookie(client, users, database):
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "administrator@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert login.status_code == 200
    refresh_token = client.cookies.get("eamms_refresh")
    assert refresh_token

    logout = client.post(
        "/api/v1/auth/logout", headers={"Origin": "http://localhost:3000"}
    )
    assert logout.status_code == 204
    assert "Max-Age=0" in logout.headers["set-cookie"]
    with database() as db:
        session = db.scalar(select(RefreshSession))
        assert session is not None and session.revoked_at is not None

    client.cookies.set("eamms_refresh", refresh_token)
    assert client.post("/api/v1/auth/refresh").status_code == 401


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADMINISTRATOR.value, 201),
        (Role.ASSET_MANAGER.value, 201),
        (Role.TECHNICIAN.value, 403),
        (Role.EMPLOYEE.value, 403),
    ],
)
def test_vendor_management_permissions_for_all_roles(
    client, auth_headers, role, expected
):
    response = client.post(
        "/api/v1/vendors",
        headers=auth_headers[role],
        json={"name": f"Vendor for {role}"},
    )
    assert response.status_code == expected


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADMINISTRATOR.value, 200),
        (Role.ASSET_MANAGER.value, 403),
        (Role.TECHNICIAN.value, 403),
        (Role.EMPLOYEE.value, 403),
    ],
)
def test_user_directory_is_admin_only(client, auth_headers, role, expected):
    assert (
        client.get("/api/v1/users", headers=auth_headers[role]).status_code == expected
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (Role.ADMINISTRATOR.value, 200),
        (Role.ASSET_MANAGER.value, 200),
        (Role.TECHNICIAN.value, 403),
        (Role.EMPLOYEE.value, 403),
    ],
)
def test_allocation_directory_permissions_for_all_roles(
    client, auth_headers, role, expected
):
    assert (
        client.get("/api/v1/users/directory", headers=auth_headers[role]).status_code
        == expected
    )


def test_validation_errors_do_not_echo_password(client):
    response = client.post(
        "/api/v1/auth/login", json={"email": "invalid", "password": "sentinel-secret"}
    )
    assert response.status_code == 422
    assert "sentinel-secret" not in response.text
    assert '"input"' not in response.text


def test_login_rate_limit_blocks_repeated_invalid_passwords(client, users, database):
    payload = {"email": "administrator@example.com", "password": "wrong-password"}
    statuses = [
        client.post("/api/v1/auth/login", json=payload).status_code for _ in range(5)
    ]
    assert statuses == [401, 401, 401, 401, 429]
    blocked = client.post(
        "/api/v1/auth/login",
        json={
            "email": "administrator@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert "administrator@example.com" not in blocked.text
    with database() as db:
        buckets = db.query(LoginThrottleBucket).all()
        assert len(buckets) == 2
        assert all("administrator@example.com" not in row.bucket_key for row in buckets)
        assert all("testclient" not in row.bucket_key for row in buckets)


def test_successful_login_clears_pair_failures(client, users, database):
    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "administrator@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
    success = client.post(
        "/api/v1/auth/login",
        json={
            "email": "administrator@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    assert success.status_code == 200
    with database() as db:
        buckets = db.query(LoginThrottleBucket).all()
        assert len(buckets) == 1
        assert buckets[0].failure_count == 2


def test_last_active_administrator_cannot_be_demoted_or_deactivated(
    client, users, auth_headers
):
    user_id = users[Role.ADMINISTRATOR.value]
    demote = client.patch(
        f"/api/v1/users/{user_id}",
        headers=auth_headers[Role.ADMINISTRATOR.value],
        json={"role": Role.EMPLOYEE.value},
    )
    assert demote.status_code == 409
    self_deactivate = client.patch(
        f"/api/v1/users/{user_id}",
        headers=auth_headers[Role.ADMINISTRATOR.value],
        json={"is_active": False},
    )
    assert self_deactivate.status_code == 400


def test_duplicate_user_email_returns_conflict(client, auth_headers):
    payload = {
        "full_name": "Second Administrator",
        "email": "administrator@example.com",
        "password": "different-correct-horse-battery",
        "role": "employee",
    }
    response = client.post(
        "/api/v1/users", headers=auth_headers[Role.ADMINISTRATOR.value], json=payload
    )
    assert response.status_code == 409


def test_user_update_rejects_explicit_null_role(client, users, auth_headers):
    response = client.patch(
        f"/api/v1/users/{users[Role.EMPLOYEE.value]}",
        headers=auth_headers[Role.ADMINISTRATOR.value],
        json={"role": None},
    )
    assert response.status_code == 422
