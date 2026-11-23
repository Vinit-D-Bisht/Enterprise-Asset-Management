from datetime import date
from decimal import Decimal

from app.models import Asset, Role
from app.services.depreciation import depreciation_values


def test_work_order_request_assignment_and_completion(
    client, users, auth_headers, basic_asset
):
    asset_id = basic_asset["id"]
    employee_headers = auth_headers[Role.EMPLOYEE.value]
    request = client.post(
        "/api/v1/work-orders",
        headers=employee_headers,
        json={"asset_id": asset_id, "title": "Screen flicker", "priority": "high"},
    )
    assert request.status_code == 201, request.text
    order_id = request.json()["id"]
    assert request.json()["status"] == "open"

    manager = auth_headers[Role.ASSET_MANAGER.value]
    assign = client.patch(
        f"/api/v1/work-orders/{order_id}/assign",
        headers=manager,
        json={
            "assigned_to_id": str(users[Role.TECHNICIAN.value]),
            "due_date": "2026-12-01",
        },
    )
    assert assign.status_code == 200

    technician = auth_headers[Role.TECHNICIAN.value]
    assert (
        client.get(f"/api/v1/work-orders/{order_id}", headers=technician).status_code
        == 200
    )
    start = client.patch(
        f"/api/v1/work-orders/{order_id}/status",
        headers=technician,
        json={"status": "in_progress"},
    )
    assert start.status_code == 200
    missing_resolution = client.patch(
        f"/api/v1/work-orders/{order_id}/status",
        headers=technician,
        json={"status": "completed"},
    )
    assert missing_resolution.status_code == 422
    complete = client.patch(
        f"/api/v1/work-orders/{order_id}/status",
        headers=technician,
        json={"status": "completed", "resolution": "Replaced display cable"},
    )
    assert complete.status_code == 200 and complete.json()["status"] == "completed"
    assert (
        client.get("/api/v1/notifications", headers=employee_headers).json()["total"]
        >= 1
    )


def test_technician_cannot_update_unassigned_work_order(
    client, auth_headers, basic_asset
):
    response = client.post(
        "/api/v1/work-orders",
        headers=auth_headers[Role.EMPLOYEE.value],
        json={"asset_id": basic_asset["id"], "title": "Check fan"},
    )
    order_id = response.json()["id"]
    denied = client.patch(
        f"/api/v1/work-orders/{order_id}/status",
        headers=auth_headers[Role.TECHNICIAN.value],
        json={"status": "in_progress"},
    )
    assert denied.status_code == 403
    employee_denied = client.patch(
        f"/api/v1/work-orders/{order_id}/status",
        headers=auth_headers[Role.EMPLOYEE.value],
        json={"status": "in_progress"},
    )
    assert employee_denied.status_code == 403


def test_depreciation_straight_line_bounds_and_rounding():
    asset = Asset(
        purchase_cost=Decimal("1200.00"),
        residual_value=Decimal("200.00"),
        useful_life_months=60,
        purchase_date=date(2020, 1, 1),
    )
    at_purchase = depreciation_values(asset, date(2020, 1, 1))
    after_full_life = depreciation_values(asset, date(2030, 1, 1))
    before_purchase = depreciation_values(asset, date(2019, 1, 1))
    assert at_purchase == (Decimal("0.00"), Decimal("1200.00"))
    assert after_full_life == (Decimal("1000.00"), Decimal("200.00"))
    assert before_purchase == (Decimal("0.00"), Decimal("1200.00"))


def test_reports_are_role_protected_and_use_real_database_counts(
    client, auth_headers, basic_asset
):
    manager = auth_headers[Role.ASSET_MANAGER.value]
    dashboard = client.get("/api/v1/reports/dashboard", headers=manager)
    assert dashboard.status_code == 200
    assert dashboard.json()["total_assets"] == 1
    assert dashboard.json()["available_assets"] == 1
    depreciation = client.get(
        "/api/v1/reports/depreciation?as_of_date=2025-01-01", headers=manager
    )
    assert depreciation.status_code == 200
    # The purchase anniversary includes the 2024 leap day under daily proration.
    assert depreciation.json()["total_book_value"] == "999.59"
    assert (
        client.get(
            "/api/v1/reports/dashboard", headers=auth_headers[Role.EMPLOYEE.value]
        ).status_code
        == 403
    )
    assert client.get("/api/v1/reports/audit", headers=manager).status_code == 403
