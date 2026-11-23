from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import manager_or_admin
from app.database.session import get_db
from app.models import User, Vendor
from app.schemas.common import Page
from app.schemas.vendors import VendorInput, VendorOutput, VendorUpdate
from app.services.audit import record_audit

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=Page[VendorOutput])
def list_vendors(
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
):
    query = select(Vendor)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Vendor.name.ilike(term),
                Vendor.email.ilike(term),
                Vendor.contact_name.ilike(term),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    vendors = db.scalars(
        query.order_by(Vendor.name).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return Page[VendorOutput](
        items=vendors, total=total, page=page, page_size=page_size
    )


@router.post("", response_model=VendorOutput, status_code=201)
def create_vendor(
    data: VendorInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    vendor = Vendor(**data.model_dump())
    db.add(vendor)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Vendor name already exists") from exc
    record_audit(db, actor.id, "vendor.created", "vendor", vendor.id)
    db.commit()
    db.refresh(vendor)
    return vendor


@router.patch("/{vendor_id}", response_model=VendorOutput)
def update_vendor(
    vendor_id: UUID,
    data: VendorUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    vendor = db.get(Vendor, vendor_id)
    if vendor is None:
        raise HTTPException(404, "Vendor not found")
    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(vendor, key, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Vendor name already exists") from exc
    record_audit(db, actor.id, "vendor.updated", "vendor", vendor.id, changes)
    db.commit()
    db.refresh(vendor)
    return vendor
