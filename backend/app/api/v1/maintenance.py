from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, manager_or_admin
from app.database.session import get_db
from app.models import MaintenancePlan, Notification, User, WorkOrder
from app.schemas.common import Page
from app.schemas.maintenance import (
    MaintenancePlanInput,
    MaintenancePlanOutput,
    NotificationOutput,
    WorkOrderAssignInput,
    WorkOrderInput,
    WorkOrderOutput,
    WorkOrderStatusInput,
)
from app.services.maintenance import (
    assign_work_order,
    can_view_work_order,
    create_plan,
    create_work_order,
    update_work_order,
    visible_work_orders,
)

router = APIRouter(tags=["maintenance"])


def order_payload(order: WorkOrder) -> WorkOrderOutput:
    return WorkOrderOutput(
        id=order.id,
        asset_id=order.asset_id,
        asset_tag=order.asset.asset_tag,
        plan_id=order.plan_id,
        title=order.title,
        description=order.description,
        priority=order.priority,
        status=order.status,
        requested_by_id=order.requested_by_id,
        assigned_to_id=order.assigned_to_id,
        due_date=order.due_date,
        completed_at=order.completed_at,
        resolution=order.resolution,
    )


@router.get("/maintenance-plans", response_model=list[MaintenancePlanOutput])
def list_plans(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(
        select(MaintenancePlan).order_by(MaintenancePlan.next_due_date)
    ).all()


@router.post(
    "/maintenance-plans", response_model=MaintenancePlanOutput, status_code=201
)
def add_plan(
    data: MaintenancePlanInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    return create_plan(db, data, actor)


@router.get("/work-orders", response_model=Page[WorkOrderOutput])
def list_work_orders(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    query = visible_work_orders(db, actor)
    if status_filter:
        query = query.where(WorkOrder.status == status_filter)
    total = (
        db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        or 0
    )
    orders = db.scalars(
        query.order_by(WorkOrder.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return Page[WorkOrderOutput](
        items=[order_payload(item) for item in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/work-orders", response_model=WorkOrderOutput, status_code=201)
def add_work_order(
    data: WorkOrderInput,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return order_payload(create_work_order(db, data, actor))


@router.get("/work-orders/{order_id}", response_model=WorkOrderOutput)
def get_work_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    order = db.scalar(select(WorkOrder).where(WorkOrder.id == order_id))
    if order is None:
        raise HTTPException(404, "Work order not found")
    if not can_view_work_order(order, actor):
        raise HTTPException(403, "You cannot view this work order")
    return order_payload(order)


@router.patch("/work-orders/{order_id}/assign", response_model=WorkOrderOutput)
def assign_order(
    order_id: UUID,
    data: WorkOrderAssignInput,
    db: Session = Depends(get_db),
    actor: User = Depends(manager_or_admin),
):
    return order_payload(
        assign_work_order(db, order_id, data.assigned_to_id, data.due_date, actor)
    )


@router.patch("/work-orders/{order_id}/status", response_model=WorkOrderOutput)
def change_order_status(
    order_id: UUID,
    data: WorkOrderStatusInput,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    return order_payload(
        update_work_order(db, order_id, data.status, data.resolution, actor)
    )


@router.get("/notifications", response_model=Page[NotificationOutput])
def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    query = select(Notification).where(Notification.user_id == actor.id)
    if unread_only:
        query = query.where(Notification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


@router.post("/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != actor.id:
        raise HTTPException(404, "Notification not found")
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
