from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Asset,
    AssetStatus,
    Assignment,
    MaintenancePlan,
    Role,
    User,
    WorkOrder,
    WorkOrderStatus,
)
from app.schemas.maintenance import MaintenancePlanInput, WorkOrderInput
from app.services.audit import notify, record_audit


def create_plan(
    db: Session, data: MaintenancePlanInput, actor: User
) -> MaintenancePlan:
    asset = db.get(Asset, data.asset_id)
    if asset is None:
        raise HTTPException(404, "Asset not found")
    plan = MaintenancePlan(**data.model_dump())
    db.add(plan)
    db.flush()
    record_audit(
        db,
        actor.id,
        "maintenance_plan.created",
        "maintenance_plan",
        plan.id,
        {"asset_id": str(asset.id)},
    )
    db.commit()
    db.refresh(plan)
    return plan


def create_work_order(db: Session, data: WorkOrderInput, actor: User) -> WorkOrder:
    asset = db.scalar(select(Asset).where(Asset.id == data.asset_id).with_for_update())
    if asset is None:
        raise HTTPException(404, "Asset not found")
    if asset.status == AssetStatus.RETIRED.value:
        raise HTTPException(409, "Cannot create work orders for retired assets")
    if data.plan_id:
        plan = db.get(MaintenancePlan, data.plan_id)
        if plan is None or not plan.is_active or plan.asset_id != asset.id:
            raise HTTPException(
                422, "Maintenance plan must be active and belong to the selected asset"
            )
    order = WorkOrder(**data.model_dump(), requested_by_id=actor.id)
    db.add(order)
    db.flush()
    refresh_asset_status(db, asset)
    record_audit(
        db,
        actor.id,
        "work_order.created",
        "work_order",
        order.id,
        {"asset_id": str(asset.id)},
    )
    if actor.role in {Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value}:
        recipients = db.scalars(
            select(User).where(
                User.role == Role.TECHNICIAN.value, User.is_active.is_(True)
            )
        ).all()
    else:
        recipients = db.scalars(
            select(User).where(
                User.role.in_([Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value]),
                User.is_active.is_(True),
            )
        ).all()
    for recipient in recipients:
        notify(
            db,
            recipient.id,
            "New work order",
            f"{order.title} for asset {asset.asset_tag} needs attention.",
        )
    db.commit()
    db.refresh(order)
    return order


def assign_work_order(
    db: Session, order_id: UUID, assignee_id: UUID, due_date: date | None, actor: User
) -> WorkOrder:
    order = db.scalar(
        select(WorkOrder).where(WorkOrder.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(404, "Work order not found")
    if order.status in {
        WorkOrderStatus.COMPLETED.value,
        WorkOrderStatus.CANCELLED.value,
    }:
        raise HTTPException(409, "Closed work orders cannot be assigned")
    assignee = db.get(User, assignee_id)
    if (
        assignee is None
        or not assignee.is_active
        or assignee.role != Role.TECHNICIAN.value
    ):
        raise HTTPException(422, "Assignee must be an active technician")
    order.assigned_to_id = assignee.id
    if due_date is not None:
        order.due_date = due_date
    record_audit(
        db,
        actor.id,
        "work_order.assigned",
        "work_order",
        order.id,
        {"assignee_id": str(assignee.id)},
    )
    notify(db, assignee.id, "Work order assigned", f"You were assigned: {order.title}.")
    db.commit()
    db.refresh(order)
    return order


def update_work_order(
    db: Session,
    order_id: UUID,
    new_status: str,
    resolution: str | None,
    actor: User,
) -> WorkOrder:
    order = db.scalar(
        select(WorkOrder).where(WorkOrder.id == order_id).with_for_update()
    )
    if order is None:
        raise HTTPException(404, "Work order not found")
    if actor.role == Role.TECHNICIAN.value and order.assigned_to_id != actor.id:
        raise HTTPException(
            403, "Technicians can update only work orders assigned to them"
        )
    if actor.role == Role.EMPLOYEE.value:
        raise HTTPException(
            403, "Employees can request maintenance but cannot update work orders"
        )
    if order.status in {
        WorkOrderStatus.COMPLETED.value,
        WorkOrderStatus.CANCELLED.value,
    }:
        raise HTTPException(409, "Closed work orders cannot be changed")
    if new_status == WorkOrderStatus.COMPLETED.value and not (
        resolution and resolution.strip()
    ):
        raise HTTPException(422, "A resolution is required to complete a work order")
    if (
        new_status == WorkOrderStatus.IN_PROGRESS.value
        and order.status != WorkOrderStatus.OPEN.value
    ):
        raise HTTPException(409, "Only open work orders can be started")
    order.status = new_status
    if resolution is not None:
        order.resolution = resolution.strip()
    if new_status == WorkOrderStatus.COMPLETED.value:
        order.completed_at = datetime.now(timezone.utc)
        asset = db.scalar(
            select(Asset).where(Asset.id == order.asset_id).with_for_update()
        )
        refresh_asset_status(db, asset, current_order_id=order.id)
        if order.plan_id:
            plan = db.get(MaintenancePlan, order.plan_id)
            if plan and plan.is_active:
                plan.next_due_date = max(plan.next_due_date, date.today()) + timedelta(
                    days=plan.interval_days
                )
        notify(
            db,
            order.requested_by_id,
            "Work order completed",
            f"{order.title} has been completed.",
        )
    elif new_status == WorkOrderStatus.CANCELLED.value:
        asset = db.scalar(
            select(Asset).where(Asset.id == order.asset_id).with_for_update()
        )
        refresh_asset_status(db, asset, current_order_id=order.id)
    record_audit(
        db,
        actor.id,
        f"work_order.{new_status}",
        "work_order",
        order.id,
        {"resolution": resolution} if resolution else {},
    )
    db.commit()
    db.refresh(order)
    return order


def refresh_asset_status(
    db: Session, asset: Asset, current_order_id: UUID | None = None
) -> None:
    active_assignment = db.scalar(
        select(Assignment.id).where(
            Assignment.asset_id == asset.id, Assignment.returned_at.is_(None)
        )
    )
    open_orders = select(WorkOrder.id).where(
        WorkOrder.asset_id == asset.id,
        WorkOrder.status.in_(
            [WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value]
        ),
    )
    if current_order_id:
        open_orders = open_orders.where(WorkOrder.id != current_order_id)
    has_open_work = db.scalar(open_orders.limit(1)) is not None
    asset.status = (
        AssetStatus.ASSIGNED.value
        if active_assignment
        else AssetStatus.IN_REPAIR.value
        if has_open_work
        else AssetStatus.AVAILABLE.value
    )


def visible_work_orders(db: Session, actor: User):
    query = select(WorkOrder).options(selectinload(WorkOrder.asset))
    if actor.role == Role.TECHNICIAN.value:
        query = query.where(WorkOrder.assigned_to_id == actor.id)
    elif actor.role == Role.EMPLOYEE.value:
        query = query.where(WorkOrder.requested_by_id == actor.id)
    return query


def can_view_work_order(order: WorkOrder, actor: User) -> bool:
    if actor.role in {Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value}:
        return True
    if actor.role == Role.TECHNICIAN.value:
        return order.assigned_to_id == actor.id
    return order.requested_by_id == actor.id
