from app.models import Role


def test_asset_allocation_return_transfer_warranty_qr_and_audit(
    client, users, auth_headers, basic_asset
):
    manager = auth_headers[Role.ASSET_MANAGER.value]
    employee_id = str(users[Role.EMPLOYEE.value])
    asset_id = basic_asset["id"]

    allocated = client.post(
        f"/api/v1/assets/{asset_id}/allocate",
        headers=manager,
        json={"user_id": employee_id, "notes": "Laptop issued for project"},
    )
    assert allocated.status_code == 201, allocated.text
    assert allocated.json()["user_id"] == employee_id
    manager_asset = client.get(f"/api/v1/assets/{asset_id}", headers=manager)
    assert manager_asset.json()["company_currency"] == "INR"

    duplicate = client.post(
        f"/api/v1/assets/{asset_id}/allocate",
        headers=manager,
        json={"user_id": employee_id},
    )
    assert duplicate.status_code == 409

    employee_headers = auth_headers[Role.EMPLOYEE.value]
    visible = client.get("/api/v1/assets", headers=employee_headers).json()["items"][0]
    assert "purchase_cost" not in visible
    assert visible["current_assignee_id"] is None
    assert visible["current_assignee_name"] is None
    history = client.get(
        f"/api/v1/assets/{asset_id}/assignments", headers=employee_headers
    )
    assert history.status_code == 200 and len(history.json()) == 1

    location = client.post(
        "/api/v1/locations", headers=manager, json={"name": "Branch", "code": "BR"}
    )
    transfer = client.post(
        f"/api/v1/assets/{asset_id}/transfer",
        headers=manager,
        json={"to_location_id": location.json()["id"], "reason": "Office move"},
    )
    assert transfer.status_code == 201

    warranty = client.post(
        f"/api/v1/assets/{asset_id}/warranties",
        headers=manager,
        json={
            "start_date": "2024-01-01",
            "end_date": "2027-01-01",
            "terms": "Parts and labor",
        },
    )
    assert warranty.status_code == 201
    assert (
        client.get(
            f"/api/v1/assets/{asset_id}/warranties", headers=employee_headers
        ).json()[0]["terms"]
        == "Parts and labor"
    )
    qr = client.get(f"/api/v1/assets/{asset_id}/qr", headers=employee_headers)
    assert (
        qr.status_code == 200
        and qr.headers["content-type"] == "image/png"
        and qr.content.startswith(b"\x89PNG")
    )

    returned = client.post(
        f"/api/v1/assets/{asset_id}/return",
        headers=manager,
        json={"notes": "Checked in"},
    )
    assert returned.status_code == 200
    asset = client.get(f"/api/v1/assets/{asset_id}", headers=manager).json()
    assert asset["status"] == "available"
    assert asset["location_id"] == location.json()["id"]

    audits = client.get(
        "/api/v1/reports/audit", headers=auth_headers[Role.ADMINISTRATOR.value]
    )
    assert audits.status_code == 200
    actions = {row["action"] for row in audits.json()}
    assert {
        "asset.created",
        "asset.allocated",
        "asset.transferred",
        "warranty.created",
        "asset.returned",
    } <= actions


def test_duplicate_asset_tag_and_invalid_financial_values(
    client, auth_headers, basic_asset
):
    manager = auth_headers[Role.ASSET_MANAGER.value]
    category = client.get("/api/v1/categories", headers=manager).json()[0]
    location = client.get("/api/v1/locations", headers=manager).json()[0]
    payload = {
        "asset_tag": "LAP-001",
        "name": "Duplicate tag",
        "category_id": category["id"],
        "location_id": location["id"],
        "purchase_date": "2024-01-01",
        "purchase_cost": "1200.00",
        "residual_value": "200.00",
        "useful_life_months": 60,
    }
    assert (
        client.post("/api/v1/assets", headers=manager, json=payload).status_code == 409
    )
    payload["asset_tag"] = "LAP-002"
    payload["residual_value"] = "1300.00"
    response = client.post("/api/v1/assets", headers=manager, json=payload)
    assert response.status_code == 422
    assert (
        client.patch(
            f"/api/v1/assets/{basic_asset['id']}",
            headers=manager,
            json={"purchase_cost": None},
        ).status_code
        == 422
    )


def test_employee_cannot_allocate_and_cannot_view_other_users_history(
    client, users, auth_headers, basic_asset
):
    asset_id = basic_asset["id"]
    employee = auth_headers[Role.EMPLOYEE.value]
    allocation = client.post(
        f"/api/v1/assets/{asset_id}/allocate",
        headers=employee,
        json={"user_id": str(users[Role.EMPLOYEE.value])},
    )
    assert allocation.status_code == 403
    manager = auth_headers[Role.ASSET_MANAGER.value]
    client.post(
        f"/api/v1/assets/{asset_id}/allocate",
        headers=manager,
        json={"user_id": str(users[Role.EMPLOYEE.value])},
    )
    created = client.post(
        "/api/v1/users",
        headers=auth_headers[Role.ADMINISTRATOR.value],
        json={
            "full_name": "Another Employee",
            "email": "another.employee@example.com",
            "password": "another-correct-horse-battery",
            "role": "employee",
        },
    )
    assert created.status_code == 201
    other_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "another.employee@example.com",
            "password": "another-correct-horse-battery",
        },
    )
    assert other_login.status_code == 200
    denied = client.get(
        f"/api/v1/assets/{asset_id}/assignments",
        headers={"Authorization": f"Bearer {other_login.json()['access_token']}"},
    )
    assert denied.status_code == 403


def test_assignment_history_only_returns_requesters_own_rows(
    client, users, auth_headers, basic_asset
):
    asset_id = basic_asset["id"]
    manager = auth_headers[Role.ASSET_MANAGER.value]
    first_user = users[Role.EMPLOYEE.value]
    second_user = users[Role.TECHNICIAN.value]
    client.post(
        f"/api/v1/assets/{asset_id}/allocate",
        headers=manager,
        json={"user_id": str(first_user)},
    )
    client.post(f"/api/v1/assets/{asset_id}/return", headers=manager, json={})
    client.post(
        f"/api/v1/assets/{asset_id}/allocate",
        headers=manager,
        json={"user_id": str(second_user)},
    )
    own_history = client.get(
        f"/api/v1/assets/{asset_id}/assignments",
        headers=auth_headers[Role.EMPLOYEE.value],
    )
    assert own_history.status_code == 200
    assert len(own_history.json()) == 1
    assert own_history.json()[0]["user_id"] == str(first_user)


def test_allocation_permission_matrix_for_all_roles(
    client, users, auth_headers, basic_asset
):
    for role in (Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value):
        response = client.post(
            f"/api/v1/assets/{basic_asset['id']}/allocate",
            headers=auth_headers[role],
            json={"user_id": str(users[Role.EMPLOYEE.value])},
        )
        assert response.status_code == 201
        client.post(
            f"/api/v1/assets/{basic_asset['id']}/return",
            headers=auth_headers[role],
            json={},
        )
    for role in (Role.TECHNICIAN.value, Role.EMPLOYEE.value):
        response = client.post(
            f"/api/v1/assets/{basic_asset['id']}/allocate",
            headers=auth_headers[role],
            json={"user_id": str(users[Role.EMPLOYEE.value])},
        )
        assert response.status_code == 403
