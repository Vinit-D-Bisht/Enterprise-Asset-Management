import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import admin_only, get_current_user, manager_or_admin
from app.core.config import settings
from app.database.session import get_db
from app.models import (
    Asset,
    AssetStatus,
    Assignment,
    AuditLog,
    MaintenancePlan,
    Notification,
    User,
    Warranty,
    WorkOrder,
    WorkOrderStatus,
)
from app.schemas.reports import (
    AuditOutput,
    DashboardOutput,
    DepreciationReport,
    DepreciationRow,
    PersonalOverview,
)
from app.services.depreciation import depreciation_for_inputs, depreciation_values

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_cell(value) -> str:
    text_value = "" if value is None else str(value)
    if text_value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + text_value
    return text_value


def _csv_stream(headers: list[str], rows):
    def generate():
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\r\n")
        writer.writerow(headers)
        yield "\ufeff" + buffer.getvalue()
        for row in rows:
            buffer.seek(0)
            buffer.truncate(0)
            writer.writerow([_csv_cell(value) for value in row])
            yield buffer.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="eamms-report.csv"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


def dashboard_data(db: Session) -> DashboardOutput:
    today = date.today()
    total = db.scalar(select(func.count(Asset.id))) or 0
    available = (
        db.scalar(
            select(func.count(Asset.id)).where(
                Asset.status == AssetStatus.AVAILABLE.value
            )
        )
        or 0
    )
    assigned = (
        db.scalar(
            select(func.count(Asset.id)).where(
                Asset.status == AssetStatus.ASSIGNED.value
            )
        )
        or 0
    )
    in_repair = (
        db.scalar(
            select(func.count(Asset.id)).where(
                Asset.status == AssetStatus.IN_REPAIR.value
            )
        )
        or 0
    )
    open_orders = (
        db.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.status.in_(
                    [WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value]
                )
            )
        )
        or 0
    )
    overdue_orders = (
        db.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.status.in_(
                    [WorkOrderStatus.OPEN.value, WorkOrderStatus.IN_PROGRESS.value]
                ),
                WorkOrder.due_date < today,
            )
        )
        or 0
    )
    maintenance_due = (
        db.scalar(
            select(func.count(MaintenancePlan.id)).where(
                MaintenancePlan.is_active.is_(True),
                MaintenancePlan.next_due_date <= today,
            )
        )
        or 0
    )
    warranty_window = today + timedelta(days=30)
    warranties_expiring = (
        db.scalar(
            select(func.count(Warranty.id)).where(
                Warranty.end_date >= today, Warranty.end_date <= warranty_window
            )
        )
        or 0
    )
    return DashboardOutput(
        total_assets=total,
        available_assets=available,
        assigned_assets=assigned,
        assets_in_repair=in_repair,
        open_work_orders=open_orders,
        overdue_work_orders=overdue_orders,
        maintenance_due=maintenance_due,
        warranties_expiring_30_days=warranties_expiring,
    )


@router.get("/overview", response_model=PersonalOverview)
def personal_overview(
    db: Session = Depends(get_db), actor: User = Depends(get_current_user)
):
    assigned_assets = (
        db.scalar(
            select(func.count(Assignment.id)).where(
                Assignment.user_id == actor.id, Assignment.returned_at.is_(None)
            )
        )
        or 0
    )
    requested = (
        db.scalar(
            select(func.count(WorkOrder.id)).where(
                WorkOrder.requested_by_id == actor.id
            )
        )
        or 0
    )
    assigned = (
        db.scalar(
            select(func.count(WorkOrder.id)).where(WorkOrder.assigned_to_id == actor.id)
        )
        or 0
    )
    unread = (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == actor.id, Notification.read_at.is_(None)
            )
        )
        or 0
    )
    return PersonalOverview(
        assigned_assets=assigned_assets,
        requested_work_orders=requested,
        assigned_work_orders=assigned,
        unread_notifications=unread,
    )


@router.get("/dashboard", response_model=DashboardOutput)
def dashboard(db: Session = Depends(get_db), _: User = Depends(manager_or_admin)):
    return dashboard_data(db)


@router.get("/depreciation", response_model=DepreciationReport)
def depreciation_report(
    as_of_date: date = Query(default_factory=date.today),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
):
    total = db.scalar(select(func.count(Asset.id))) or 0
    assets = db.scalars(
        select(Asset)
        .order_by(Asset.asset_tag)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items: list[DepreciationRow] = []
    for asset in assets:
        accumulated, book_value = depreciation_values(asset, as_of_date)
        items.append(
            DepreciationRow(
                asset_id=asset.id,
                asset_tag=asset.asset_tag,
                name=asset.name,
                purchase_cost=Decimal(asset.purchase_cost),
                residual_value=Decimal(asset.residual_value),
                accumulated_depreciation=accumulated,
                book_value=book_value,
                as_of_date=as_of_date,
            )
        )
    # Totals describe the whole register, even when row details are paginated.
    all_assets = db.execute(
        select(
            Asset.purchase_cost,
            Asset.residual_value,
            Asset.useful_life_months,
            Asset.purchase_date,
        )
    ).all()
    total_cost = Decimal("0")
    total_accumulated = Decimal("0")
    total_book = Decimal("0")
    for cost, residual, useful_life_months, purchase_date in all_assets:
        total_cost += Decimal(cost)
        accumulated, book = depreciation_for_inputs(
            cost, residual, useful_life_months, purchase_date, as_of_date
        )
        total_accumulated += accumulated
        total_book += book
    return DepreciationReport(
        as_of_date=as_of_date,
        company_currency=settings.COMPANY_CURRENCY,
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_cost=total_cost,
        total_accumulated_depreciation=total_accumulated,
        total_book_value=total_book,
    )


@router.get("/depreciation.csv")
def export_depreciation_csv(
    as_of_date: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    _: User = Depends(manager_or_admin),
):
    def rows():
        assets = db.scalars(
            select(Asset).order_by(Asset.asset_tag).execution_options(yield_per=500)
        )
        for asset in assets:
            accumulated, book_value = depreciation_values(asset, as_of_date)
            yield (
                asset.asset_tag,
                asset.name,
                asset.purchase_cost,
                asset.residual_value,
                accumulated,
                book_value,
                settings.COMPANY_CURRENCY,
                as_of_date.isoformat(),
            )

    response = _csv_stream(
        [
            "asset_tag",
            "name",
            "purchase_cost",
            "residual_value",
            "accumulated_depreciation",
            "book_value",
            "currency",
            "as_of_date",
        ],
        rows(),
    )
    response.headers["Content-Disposition"] = (
        'attachment; filename="eamms-depreciation.csv"'
    )
    return response


@router.get("/audit", response_model=list[AuditOutput])
def audit_report(
    entity_type: str | None = None,
    entity_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    return db.scalars(
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()


@router.get("/audit.csv")
def export_audit_csv(
    entity_type: str | None = None,
    entity_id: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(admin_only),
):
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)

    def rows():
        for event in db.scalars(
            query.order_by(AuditLog.created_at.desc()).execution_options(yield_per=500)
        ):
            yield (
                event.created_at.isoformat(),
                event.action,
                event.entity_type,
                event.entity_id,
                event.actor_id,
            )

    response = _csv_stream(
        ["created_at", "action", "entity_type", "entity_id", "actor_id"], rows()
    )
    response.headers["Content-Disposition"] = 'attachment; filename="eamms-audit.csv"'
    return response
