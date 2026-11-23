from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import admin_only, manager_or_admin
from app.database.session import get_db
from app.models import User
from app.schemas.auth import UserCreate, UserOptionOutput, UserOutput, UserUpdate
from app.schemas.common import Page
from app.services.auth import create_user, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/directory", response_model=list[UserOptionOutput])
def list_user_directory(
    db: Session = Depends(get_db), _: User = Depends(manager_or_admin)
):
    return db.scalars(
        select(User).where(User.is_active.is_(True)).order_by(User.full_name)
    ).all()


@router.get("", response_model=Page[UserOutput])
def list_users(
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(User)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(User.full_name.ilike(term), User.normalized_email.ilike(term))
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    users = db.scalars(
        query.order_by(User.full_name).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page[UserOutput](items=users, total=total, page=page, page_size=page_size)


@router.post("", response_model=UserOutput, status_code=201)
def add_user(
    data: UserCreate, db: Session = Depends(get_db), actor: User = Depends(admin_only)
):
    return create_user(db, data, actor)


@router.patch("/{user_id}", response_model=UserOutput)
def patch_user(
    user_id: UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_only),
):
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(404, "User not found")
    return update_user(db, target, data.model_dump(exclude_unset=True), actor)
