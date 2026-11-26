from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import admin_only
from app.database.session import get_db
from app.models import Department, User
from app.schemas.departments import DepartmentCreate, DepartmentOutput, DepartmentUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/departments", tags=["departments"])


def _output(db: Session, department: Department) -> dict:
    count = (
        db.scalar(
            select(func.count(User.id)).where(User.department_id == department.id)
        )
        or 0
    )
    return {
        "id": department.id,
        "name": department.name,
        "description": department.description,
        "employee_count": count,
    }


@router.get("", response_model=list[DepartmentOutput])
def list_departments(
    search: str | None = Query(default=None, max_length=120),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(Department)
    if search and search.strip():
        query = query.where(Department.name.ilike(f"%{search.strip()}%"))
    rows = db.scalars(query.order_by(Department.name)).all()
    return [_output(db, row) for row in rows]


@router.post("", response_model=DepartmentOutput, status_code=status.HTTP_201_CREATED)
def create_department(
    data: DepartmentCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    department = Department(name=data.name, description=data.description)
    db.add(department)
    try:
        db.flush()
        record_audit(db, actor.id, "department.created", "department", department.id)
        db.commit()
        db.refresh(department)
        return _output(db, department)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A department with this name already exists") from exc


@router.patch("/{department_id}", response_model=DepartmentOutput)
def update_department(
    department_id: UUID,
    data: DepartmentUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(404, "Department not found")
    changes = data.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(department, field, value)
    try:
        db.flush()
        record_audit(
            db, actor.id, "department.updated", "department", department.id, changes
        )
        db.commit()
        db.refresh(department)
        return _output(db, department)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "A department with this name already exists") from exc


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    department = db.scalar(
        select(Department).where(Department.id == department_id).with_for_update()
    )
    if department is None:
        raise HTTPException(404, "Department not found")
    if db.scalar(select(User.id).where(User.department_id == department.id).limit(1)):
        raise HTTPException(
            409, "Department is assigned to employees; reassign them before deleting it"
        )
    record_audit(
        db,
        actor.id,
        "department.deleted",
        "department",
        department.id,
        {"name": department.name},
    )
    db.delete(department)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
