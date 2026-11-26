from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models import AuditLog, Role, User


def test_department_crud_and_audit(client, auth_headers, database):
    admin = auth_headers[Role.ADMINISTRATOR.value]
    created = client.post(
        "/api/v1/departments",
        headers=admin,
        json={"name": "  Finance  ", "description": "  Accounts  "},
    )
    assert created.status_code == 201, created.text
    department = created.json()
    assert department["name"] == "Finance" and department["description"] == "Accounts"
    assert department["employee_count"] == 0
    updated = client.patch(
        f"/api/v1/departments/{department['id']}",
        headers=admin,
        json={"name": "Financial Operations"},
    )
    assert (
        updated.status_code == 200 and updated.json()["name"] == "Financial Operations"
    )
    assert (
        client.get("/api/v1/departments?search=financial", headers=admin).json()[0][
            "id"
        ]
        == department["id"]
    )
    assert (
        client.delete(
            f"/api/v1/departments/{department['id']}", headers=admin
        ).status_code
        == 204
    )
    with database() as db:
        actions = set(
            db.scalars(
                select(AuditLog.action).where(AuditLog.entity_type == "department")
            )
        )
        assert actions == {
            "department.created",
            "department.updated",
            "department.deleted",
        }


@pytest.mark.parametrize(
    "role", [Role.ASSET_MANAGER.value, Role.TECHNICIAN.value, Role.EMPLOYEE.value]
)
def test_department_management_requires_admin(client, auth_headers, role):
    headers = auth_headers[role]
    assert client.get("/api/v1/departments", headers=headers).status_code == 403
    assert (
        client.post(
            "/api/v1/departments", headers=headers, json={"name": "Operations"}
        ).status_code
        == 403
    )


def test_department_management_requires_authentication(client):
    assert client.get("/api/v1/departments").status_code == 401
    assert (
        client.post("/api/v1/departments", json={"name": "Operations"}).status_code
        == 401
    )


def test_department_names_are_case_insensitively_unique(client, auth_headers):
    headers = auth_headers[Role.ADMINISTRATOR.value]
    assert (
        client.post(
            "/api/v1/departments", headers=headers, json={"name": "Finance"}
        ).status_code
        == 201
    )
    duplicate = client.post(
        "/api/v1/departments", headers=headers, json={"name": " finance "}
    )
    assert duplicate.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [{"name": " "}, {"name": "A" * 121}, {"name": "Legal", "extra": "not allowed"}, {}],
)
def test_department_validation(client, auth_headers, payload):
    assert (
        client.post(
            "/api/v1/departments",
            headers=auth_headers[Role.ADMINISTRATOR.value],
            json=payload,
        ).status_code
        == 422
    )


def test_department_delete_conflicts_when_employee_references_it(
    client, auth_headers, database
):
    admin = auth_headers[Role.ADMINISTRATOR.value]
    department = client.post(
        "/api/v1/departments", headers=admin, json={"name": "Engineering"}
    ).json()
    with database() as db:
        db.add(
            User(
                full_name="Assigned Employee",
                email="assigned@example.com",
                normalized_email="assigned@example.com",
                password_hash=hash_password("correct-horse-battery-staple"),
                role=Role.EMPLOYEE.value,
                is_active=True,
                department_id=UUID(department["id"]),
            )
        )
        db.commit()
    response = client.delete(f"/api/v1/departments/{department['id']}", headers=admin)
    assert response.status_code == 409
    assert "reassign" in response.json()["detail"]


def test_users_can_be_created_and_reassigned_to_departments(
    client, auth_headers, database
):
    admin = auth_headers[Role.ADMINISTRATOR.value]
    department = client.post(
        "/api/v1/departments", headers=admin, json={"name": "People"}
    ).json()
    created = client.post(
        "/api/v1/users",
        headers=admin,
        json={
            "full_name": "Department Employee",
            "email": "dept@example.com",
            "password": "correct-horse-battery-staple",
            "role": "employee",
            "department_id": department["id"],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["department_id"] == department["id"]
    assert created.json()["department_name"] == "People"
    cleared = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=admin,
        json={"department_id": None},
    )
    assert cleared.status_code == 200 and cleared.json()["department_id"] is None
    reassigned = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=admin,
        json={"department_id": department["id"]},
    )
    assert reassigned.status_code == 200
    assert reassigned.json()["department_id"] == department["id"]
    with database() as db:
        update_log = db.scalar(
            select(AuditLog)
            .where(
                AuditLog.action == "user.updated",
                AuditLog.entity_id == created.json()["id"],
            )
            .order_by(AuditLog.created_at.desc())
        )
        assert update_log is not None
        assert update_log.details["department_id"] == department["id"]
    assert (
        client.post(
            "/api/v1/users",
            headers=admin,
            json={
                "full_name": "Unknown Department",
                "email": "unknown-dept@example.com",
                "password": "correct-horse-battery-staple",
                "role": "employee",
                "department_id": str(uuid4()),
            },
        ).status_code
        == 422
    )
