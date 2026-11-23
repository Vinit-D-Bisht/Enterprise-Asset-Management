from io import BytesIO
from uuid import UUID

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, manager_or_admin
from app.core.config import settings
from app.database.session import get_db
from app.models import Asset, AssetCategory, Assignment, Location, Role, User, Warranty
from app.schemas.assets import (
    AssetInput,
    AssetOutput,
    AssetSummaryOutput,
    AssetUpdate,
    AssignmentInput,
    AssignmentOutput,
    CategoryInput,
    DirectoryOutput,
    LocationInput,
    ReturnInput,
    TransferInput,
    TransferOutput,
    WarrantyInput,
    WarrantyOutput,
)
from app.schemas.common import Page
from app.services.assets import (
    add_warranty,
    allocate_asset,
    create_asset,
    retire_asset,
    return_asset,
    transfer_asset,
    update_asset,
)
from app.services.audit import record_audit

router = APIRouter(tags=["assets"])


def asset_payload(asset: Asset, include_financials: bool):
    active = next(
        (
            assignment
            for assignment in asset.assignments
            if assignment.returned_at is None
        ),
        None,
    )
    common = {
        "id": asset.id,
        "asset_tag": asset.asset_tag,
        "serial_number": asset.serial_number,
        "name": asset.name,
        "description": asset.description,
        "category_id": asset.category_id,
        "category_name": asset.category.name,
        "location_id": asset.location_id,
        "location_name": asset.location.name,
        "status": asset.status,
        "current_assignee_id": active.user_id
        if active and include_financials
        else None,
        "current_assignee_name": active.user.full_name
        if active and include_financials
        else None,
    }
    if include_financials:
        common.update(
            vendor_id=asset.vendor_id,
            purchase_date=asset.purchase_date,
            purchase_cost=asset.purchase_cost,
            currency_code=settings.CURRENCY_CODE,
            residual_value=asset.residual_value,
            useful_life_months=asset.useful_life_months,
        )
        return AssetOutput(**common)
    return AssetSummaryOutput(**common)


@router.get("/categories", response_model=list[DirectoryOutput])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(AssetCategory).order_by(AssetCategory.name)).all()


@router.post("/categories", response_model=DirectoryOutput, status_code=201)
def create_category(
    data: CategoryInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    category = AssetCategory(name=data.name.strip(), description=data.description)
    db.add(category)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Category name already exists") from exc
    db.refresh(category)
    record_audit(db, actor.id, "category.created", "category", category.id)
    db.commit()
    return category


@router.get("/locations", response_model=list[DirectoryOutput])
def list_locations(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Location).order_by(Location.name)).all()


@router.post("/locations", response_model=DirectoryOutput, status_code=201)
def create_location(
    data: LocationInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    location = Location(
        name=data.name.strip(), code=data.code, description=data.description
    )
    db.add(location)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Location name or code already exists") from exc

    record_audit(db, actor.id, "location.created", "location", location.id)
    db.commit()
    db.refresh(location)
    return location


@router.get("/assets", response_model=Page[AssetOutput | AssetSummaryOutput])
def list_assets(
    search: str | None = None,
    asset_status: str | None = Query(default=None, alias="status"),
    category_id: UUID | None = None,
    location_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    query = select(Asset).options(
        selectinload(Asset.category),
        selectinload(Asset.location),
        selectinload(Asset.assignments).selectinload(Assignment.user),
    )
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Asset.name.ilike(term),
                Asset.asset_tag.ilike(term),
                Asset.serial_number.ilike(term),
            )
        )
    if asset_status:
        query = query.where(Asset.status == asset_status)
    if category_id:
        query = query.where(Asset.category_id == category_id)
    if location_id:
        query = query.where(Asset.location_id == location_id)
    total = (
        db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        or 0
    )
    assets = db.scalars(
        query.order_by(Asset.asset_tag).offset((page - 1) * page_size).limit(page_size)
    ).all()
    full = actor.role in {Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value}
    items = [asset_payload(asset, full) for asset in assets]
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/assets", response_model=AssetOutput, status_code=201)
def add_asset(
    data: AssetInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    asset = create_asset(db, data, actor)
    asset = db.scalar(
        select(Asset)
        .where(Asset.id == asset.id)
        .options(
            selectinload(Asset.category),
            selectinload(Asset.location),
            selectinload(Asset.assignments),
        )
    )
    return asset_payload(asset, True)


@router.get("/assets/{asset_id}", response_model=AssetOutput | AssetSummaryOutput)
def get_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    asset = db.scalar(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(
            selectinload(Asset.category),
            selectinload(Asset.location),
            selectinload(Asset.assignments).selectinload(Assignment.user),
        )
    )
    if asset is None:
        raise HTTPException(404, "Asset not found")
    return asset_payload(
        asset, actor.role in {Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value}
    )


@router.patch("/assets/{asset_id}", response_model=AssetOutput)
def patch_asset(
    asset_id: UUID,
    data: AssetUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    asset = update_asset(db, asset_id, data, actor)
    asset = db.scalar(
        select(Asset)
        .where(Asset.id == asset.id)
        .options(
            selectinload(Asset.category),
            selectinload(Asset.location),
            selectinload(Asset.assignments),
        )
    )
    return asset_payload(asset, True)


@router.post(
    "/assets/{asset_id}/allocate", response_model=AssignmentOutput, status_code=201
)
def allocate(
    asset_id: UUID,
    data: AssignmentInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    assignment = allocate_asset(db, asset_id, data.user_id, data.notes, actor)
    return AssignmentOutput(
        id=assignment.id,
        asset_id=assignment.asset_id,
        asset_tag=assignment.asset.asset_tag,
        user_id=assignment.user_id,
        user_name=assignment.user.full_name,
        assigned_by_id=assignment.assigned_by_id,
        assigned_at=assignment.assigned_at,
        returned_at=assignment.returned_at,
        notes=assignment.notes,
    )


@router.post("/assets/{asset_id}/return", response_model=AssignmentOutput)
def return_allocation(
    asset_id: UUID,
    data: ReturnInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    assignment = return_asset(db, asset_id, data.notes, actor)
    return AssignmentOutput(
        id=assignment.id,
        asset_id=assignment.asset_id,
        asset_tag=assignment.asset.asset_tag,
        user_id=assignment.user_id,
        user_name=assignment.user.full_name,
        assigned_by_id=assignment.assigned_by_id,
        assigned_at=assignment.assigned_at,
        returned_at=assignment.returned_at,
        notes=assignment.notes,
    )


@router.post(
    "/assets/{asset_id}/transfer", response_model=TransferOutput, status_code=201
)
def transfer(
    asset_id: UUID,
    data: TransferInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    item = transfer_asset(db, asset_id, data, actor)
    return item


@router.post("/assets/{asset_id}/retire", response_model=AssetOutput)
def retire(
    asset_id: UUID,
    reason: str = Query(min_length=3, max_length=2000),
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    asset = retire_asset(db, asset_id, reason, actor)
    asset = db.scalar(
        select(Asset)
        .where(Asset.id == asset.id)
        .options(
            selectinload(Asset.category),
            selectinload(Asset.location),
            selectinload(Asset.assignments),
        )
    )
    return asset_payload(asset, True)


@router.get("/assets/{asset_id}/assignments", response_model=list[AssignmentOutput])
def asset_assignments(
    asset_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    rows = db.scalars(
        select(Assignment)
        .where(Assignment.asset_id == asset_id)
        .options(selectinload(Assignment.user), selectinload(Assignment.asset))
        .order_by(Assignment.assigned_at.desc())
    ).all()
    if actor.role in {Role.EMPLOYEE.value, Role.TECHNICIAN.value} and not any(
        row.user_id == actor.id for row in rows
    ):
        raise HTTPException(403, "You cannot view another user's allocation history")
    return [
        AssignmentOutput(
            id=row.id,
            asset_id=row.asset_id,
            asset_tag=row.asset.asset_tag,
            user_id=row.user_id,
            user_name=row.user.full_name,
            assigned_by_id=row.assigned_by_id,
            assigned_at=row.assigned_at,
            returned_at=row.returned_at,
            notes=row.notes,
        )
        for row in rows
    ]


@router.get("/assets/{asset_id}/qr")
def asset_qr(
    asset_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    image = qrcode.make(f"eamms://asset/{asset.id}")
    output = BytesIO()
    image.save(output, format="PNG")
    return Response(
        output.getvalue(),
        media_type="image/png",
        headers={"Content-Disposition": f'inline; filename="{asset.asset_tag}.png"'},
    )


@router.post(
    "/assets/{asset_id}/warranties", response_model=WarrantyOutput, status_code=201
)
def create_warranty(
    asset_id: UUID,
    data: WarrantyInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    return add_warranty(db, asset_id, data, actor)


@router.get("/assets/{asset_id}/warranties", response_model=list[WarrantyOutput])
def list_warranties(
    asset_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    if db.get(Asset, asset_id) is None:
        raise HTTPException(404, "Asset not found")
    return db.scalars(
        select(Warranty)
        .where(Warranty.asset_id == asset_id)
        .order_by(Warranty.end_date)
    ).all()
