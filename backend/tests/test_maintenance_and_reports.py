from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import Asset, Notification, Role
from app.services.depreciation import depreciation_values
from app.tasks import notifications_scheduler


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


def test_depreciation_life_anniversary_uses_actual_leap_year_days():
    asset = Asset(
        purchase_cost=Decimal("1200.00"),
        residual_value=Decimal("200.00"),
        useful_life_months=12,
        purchase_date=date(2024, 1, 1),
    )
    midway = depreciation_values(asset, date(2024, 7, 1))
    anniversary = depreciation_values(asset, date(2025, 1, 1))
    assert midway == (Decimal("497.27"), Decimal("702.73"))
    assert anniversary == (Decimal("1000.00"), Decimal("200.00"))


def test_reminder_scheduler_covers_overdue_plans_and_deduplicates(
    client, database, auth_headers, basic_asset, monkeypatch
):
    manager = auth_headers[Role.ASSET_MANAGER.value]
    plan = client.post(
        "/api/v1/maintenance-plans",
        headers=manager,
        json={
            "name": "Annual inspection",
            "asset_id": basic_asset["id"],
            "interval_days": 365,
            "next_due_date": "2026-11-23",
        },
    )
    assert plan.status_code == 201
    monkeypatch.setattr(notifications_scheduler, "SessionLocal", database)
    assert notifications_scheduler.deliver_due_notifications(date(2026, 11, 24)) == 2
    assert notifications_scheduler.deliver_due_notifications(date(2026, 11, 24)) == 0
    with database() as db:
        rows = db.scalars(select(Notification)).all()
        assert len(rows) == 2
        assert all(row.dedupe_key for row in rows)


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
    # The actual 5-year calendar life includes the 2024 leap day.
    assert depreciation.json()["total_book_value"] == "999.67"
    assert (
        client.get(
            "/api/v1/reports/dashboard", headers=auth_headers[Role.EMPLOYEE.value]
        ).status_code
        == 403
    )
    assert client.get("/api/v1/reports/audit", headers=manager).status_code == 403
