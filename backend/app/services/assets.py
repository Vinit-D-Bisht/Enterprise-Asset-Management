from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Asset,
    AssetCategory,
    AssetStatus,
    Assignment,
    Location,
    Transfer,
    User,
    Vendor,
    Warranty,
    WorkOrder,
    WorkOrderStatus,
)
from app.schemas.assets import AssetInput, AssetUpdate, TransferInput, WarrantyInput
from app.services.audit import notify, record_audit


def get_asset_for_update(db: Session, asset_id: UUID) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id).with_for_update())
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    return asset


def validate_references(
    db: Session, category_id: UUID, location_id: UUID, vendor_id: UUID | None
) -> None:
    if db.get(AssetCategory, category_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown asset category"
        )
    if db.get(Location, location_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown location")
    if vendor_id and db.get(Vendor, vendor_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown vendor")


def create_asset(db: Session, data: AssetInput, actor: User) -> Asset:
    validate_references(db, data.category_id, data.location_id, data.vendor_id)
    asset = Asset(**data.model_dump())
    db.add(asset)
    try:
        db.flush()
        record_audit(
            db,
            actor.id,
            "asset.created",
            "asset",
            asset.id,
            {"asset_tag": asset.asset_tag},
        )
        db.commit()
        db.refresh(asset)
        return asset
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Asset tag or serial number already exists"
        ) from exc


def update_asset(db: Session, asset_id: UUID, data: AssetUpdate, actor: User) -> Asset:
    asset = get_asset_for_update(db, asset_id)
    changes = data.model_dump(exclude_unset=True)
    for key in ("category_id", "location_id", "vendor_id"):
        value = changes.get(key)
        if value is not None:
            model = {
                "category_id": AssetCategory,
                "location_id": Location,
                "vendor_id": Vendor,
            }[key]
            if db.get(model, value) is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Unknown {key.removesuffix('_id')}",
                )
    new_cost = changes.get("purchase_cost", asset.purchase_cost)
    new_residual = changes.get("residual_value", asset.residual_value)
    if new_residual > new_cost:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Residual value cannot exceed purchase cost",
        )
    if asset.status == AssetStatus.RETIRED.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Retired assets cannot be changed"
        )
    old_location = asset.location_id
    for key, value in changes.items():
        setattr(asset, key, value)
    try:
        db.flush()
        record_audit(
            db,
            actor.id,
            "asset.updated",
            "asset",
            asset.id,
            {k: str(v) for k, v in changes.items()},
        )
        if "location_id" in changes and changes["location_id"] != old_location:
            db.add(
                Transfer(
                    asset_id=asset.id,
                    from_location_id=old_location,
                    to_location_id=changes["location_id"],
                    transferred_by_id=actor.id,
                    reason="Location changed during asset update",
                )
            )
        db.commit()
        db.refresh(asset)
        return asset
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Asset update conflicts with an existing record"
        ) from exc


def allocate_asset(
    db: Session, asset_id: UUID, user_id: UUID, notes: str | None, actor: User
) -> Assignment:
    asset = get_asset_for_update(db, asset_id)
    if asset.status != AssetStatus.AVAILABLE.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only available assets can be allocated"
        )
    recipient = db.get(User, user_id)
    if recipient is None or not recipient.is_active:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Recipient is missing or inactive"
        )
    assignment = Assignment(
        asset_id=asset.id, user_id=recipient.id, assigned_by_id=actor.id, notes=notes
    )
    asset.status = AssetStatus.ASSIGNED.value
    db.add(assignment)
    try:
        db.flush()
        record_audit(
            db,
            actor.id,
            "asset.allocated",
            "asset",
            asset.id,
            {"user_id": str(user_id)},
        )
        notify(
            db,
            recipient.id,
            "Asset allocated",
            f"Asset {asset.asset_tag} was allocated to you.",
        )
        db.commit()
        db.refresh(assignment)
        return assignment
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This asset already has an active allocation"
        ) from exc


def return_asset(
    db: Session, asset_id: UUID, notes: str | None, actor: User
) -> Assignment:
    asset = get_asset_for_update(db, asset_id)
    assignment = db.scalar(
        select(Assignment)
        .where(Assignment.asset_id == asset.id, Assignment.returned_at.is_(None))
        .with_for_update()
    )
    if assignment is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Asset has no active allocation")
    assignment.returned_at = datetime.now(timezone.utc)
    if notes:
        assignment.notes = f"{assignment.notes or ''}\nReturn: {notes}".strip()
    active_work_order = db.scalar(
        select(WorkOrder.id)
        .where(
            WorkOrder.asset_id == asset.id,
            WorkOrder.status.in_(
                [WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value]
            ),
        )
        .limit(1)
    )
    asset.status = (
        AssetStatus.IN_REPAIR.value
        if active_work_order
        else AssetStatus.AVAILABLE.value
    )
    record_audit(
        db,
        actor.id,
        "asset.returned",
        "asset",
        asset.id,
        {"assignment_id": str(assignment.id)},
    )
    notify(
        db,
        assignment.user_id,
        "Asset returned",
        f"Your allocation of asset {asset.asset_tag} has been returned.",
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def transfer_asset(db: Session, asset_id: UUID, data: TransferInput, actor: User):
    asset = get_asset_for_update(db, asset_id)
    if asset.status == AssetStatus.RETIRED.value:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Retired assets cannot be transferred"
        )
    if db.get(Location, data.to_location_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown destination location"
        )
    if asset.location_id == data.to_location_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Asset is already at the requested location"
        )
    from_location_id = asset.location_id
    asset.location_id = data.to_location_id
    transfer = Transfer(
        asset_id=asset.id,
        from_location_id=from_location_id,
        to_location_id=data.to_location_id,
        transferred_by_id=actor.id,
        reason=data.reason,
    )
    db.add(transfer)
    record_audit(
        db,
        actor.id,
        "asset.transferred",
        "asset",
        asset.id,
        {"from": str(from_location_id), "to": str(data.to_location_id)},
    )
    db.commit()
    return transfer


def retire_asset(db: Session, asset_id: UUID, reason: str, actor: User) -> Asset:
    asset = get_asset_for_update(db, asset_id)
    if asset.status == AssetStatus.RETIRED.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Asset is already retired")
    if db.scalar(
        select(Assignment.id).where(
            Assignment.asset_id == asset.id, Assignment.returned_at.is_(None)
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Return the active allocation before retiring this asset",
        )
    if db.scalar(
        select(WorkOrder.id).where(
            WorkOrder.asset_id == asset.id,
            WorkOrder.status.in_(
                [WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value]
            ),
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Close active work orders before retiring this asset",
        )
    asset.status = AssetStatus.RETIRED.value
    record_audit(db, actor.id, "asset.retired", "asset", asset.id, {"reason": reason})
    db.commit()
    return asset


def add_warranty(
    db: Session, asset_id: UUID, data: WarrantyInput, actor: User
) -> Warranty:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Asset not found")
    if data.end_date < data.start_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Warranty end date must not precede start date",
        )
    if data.vendor_id and db.get(Vendor, data.vendor_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown vendor")
    warranty = Warranty(asset_id=asset.id, **data.model_dump())
    db.add(warranty)
    db.flush()
    record_audit(
        db,
        actor.id,
        "warranty.created",
        "warranty",
        warranty.id,
        {"asset_id": str(asset.id)},
    )
    db.commit()
    db.refresh(warranty)
    return warranty
