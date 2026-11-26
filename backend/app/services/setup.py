from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    Asset,
    AssetCategory,
    Assignment,
    AuditLog,
    Department,
    Location,
    MaintenancePlan,
    Notification,
    Role,
    Transfer,
    User,
    Vendor,
    Warranty,
    WorkOrder,
)
from app.schemas.setup import InitialSetupRequest

LOCK_ID = 824731902146


def setup_required(db: Session) -> bool:
    return (
        db.scalar(
            select(func.count(User.id)).where(User.role == Role.ADMINISTRATOR.value)
        )
        == 0
    )


def _sample_data(db: Session, admin: User) -> None:
    departments = {
        name: Department(name=name, description=f"{name} department")
        for name in (
            "Information Technology",
            "Finance",
            "Facilities",
            "Human Resources",
        )
    }
    locations = {
        name: Location(name=name, code=code, description=f"{name}, India")
        for name, code in (
            ("Bengaluru Head Office", "BLR-HQ"),
            ("Mumbai Branch", "MUM-01"),
            ("Pune Operations Centre", "PUN-OPS"),
        )
    }
    categories = {
        name: AssetCategory(name=name, description=f"{name} equipment")
        for name in ("Computers", "Networking", "Facilities")
    }
    db.add_all([*departments.values(), *locations.values(), *categories.values()])
    db.flush()
    vendors = [
        Vendor(
            name="Tata Consultancy Services Procurement",
            contact_name="Ananya Rao",
            email="procurement@tcs.example",
            phone="+91-80-5550-0100",
            address="Bengaluru, Karnataka",
        ),
        Vendor(
            name="Dell India",
            contact_name="Arjun Mehta",
            email="enterprise@dell.example",
            phone="+91-22-5550-0200",
            address="Mumbai, Maharashtra",
        ),
        Vendor(
            name="HP India",
            contact_name="Kavya Nair",
            email="business@hp.example",
            phone="+91-20-5550-0300",
            address="Pune, Maharashtra",
        ),
    ]
    db.add_all(vendors)
    db.flush()
    specs = [
        (
            "asset.manager@sample.eamms.invalid",
            "Aarav Sharma",
            Role.ASSET_MANAGER.value,
            "Information Technology",
        ),
        (
            "technician@sample.eamms.invalid",
            "Priya Iyer",
            Role.TECHNICIAN.value,
            "Facilities",
        ),
        (
            "employee@sample.eamms.invalid",
            "Rahul Patel",
            Role.EMPLOYEE.value,
            "Finance",
        ),
        (
            "employee2@sample.eamms.invalid",
            "Neha Kulkarni",
            Role.EMPLOYEE.value,
            "Human Resources",
        ),
    ]
    people = []
    for email, name, role, dept in specs:
        person = User(
            full_name=name,
            email=email,
            normalized_email=email,
            password_hash=hash_password(__import__("secrets").token_urlsafe(32)),
            role=role,
            is_active=False,
            department_id=departments[dept].id,
        )
        db.add(person)
        people.append(person)
    admin.department_id = departments["Information Technology"].id
    db.flush()
    today = date.today()
    assets = []
    rows = [
        (
            "EAM-LAP-001",
            "Dell Latitude 7450",
            "Computers",
            "Bengaluru Head Office",
            112500,
            12500,
            36,
            0,
            "assigned",
            people[2],
        ),
        (
            "EAM-LAP-002",
            "HP EliteBook 840",
            "Computers",
            "Bengaluru Head Office",
            98500,
            8500,
            36,
            1,
            "available",
            None,
        ),
        (
            "EAM-NET-001",
            "Cisco Catalyst Switch",
            "Networking",
            "Mumbai Branch",
            185000,
            15000,
            60,
            2,
            "in_repair",
            None,
        ),
        (
            "EAM-FAC-001",
            "Daikin Split AC 2 Ton",
            "Facilities",
            "Pune Operations Centre",
            78000,
            8000,
            84,
            0,
            "available",
            None,
        ),
        (
            "EAM-LAP-003",
            "Dell Precision 3581",
            "Computers",
            "Mumbai Branch",
            148000,
            18000,
            48,
            1,
            "assigned",
            people[3],
        ),
        (
            "EAM-NET-002",
            "Fortinet Firewall 100F",
            "Networking",
            "Bengaluru Head Office",
            265000,
            25000,
            60,
            2,
            "available",
            None,
        ),
    ]
    for (
        tag,
        name,
        category,
        location,
        cost,
        residual,
        life,
        vendor_idx,
        status,
        assigned,
    ) in rows:
        purchase_date = today - timedelta(days=365 + vendor_idx * 125)
        asset = Asset(
            asset_tag=tag,
            name=name,
            description=f"Company equipment: {name}",
            category_id=categories[category].id,
            location_id=locations[location].id,
            vendor_id=vendors[vendor_idx].id,
            purchase_date=purchase_date,
            purchase_cost=cost,
            residual_value=residual,
            useful_life_months=life,
            status=status,
        )
        db.add(asset)
        assets.append((asset, assigned))
    db.flush()
    for asset, assigned in assets:
        if assigned:
            db.add(
                Assignment(
                    asset_id=asset.id,
                    user_id=assigned.id,
                    assigned_by_id=admin.id,
                    notes="Sample active allocation",
                )
            )
    # Past assignment preserved as a closed history record.
    db.add(
        Assignment(
            asset_id=assets[1][0].id,
            user_id=people[2].id,
            assigned_by_id=admin.id,
            assigned_at=__import__("datetime").datetime.combine(
                today - timedelta(days=180),
                __import__("datetime").time(),
                tzinfo=__import__("datetime").timezone.utc,
            ),
            returned_at=__import__("datetime").datetime.combine(
                today - timedelta(days=90),
                __import__("datetime").time(),
                tzinfo=__import__("datetime").timezone.utc,
            ),
            notes="Sample returned allocation",
        )
    )
    plan = MaintenancePlan(
        name="Quarterly HVAC inspection",
        asset_id=assets[3][0].id,
        interval_days=90,
        next_due_date=today + timedelta(days=15),
        description="Inspect filters, coils, and cooling performance",
        is_active=True,
    )
    db.add(plan)
    db.flush()
    orders = [
        WorkOrder(
            asset_id=assets[2][0].id,
            title="Inspect network switch",
            description="Intermittent port connectivity reported",
            priority="high",
            status="open",
            requested_by_id=people[1].id,
            assigned_to_id=people[1].id,
            due_date=today + timedelta(days=2),
        ),
        WorkOrder(
            asset_id=assets[3][0].id,
            plan_id=plan.id,
            title="Quarterly HVAC inspection",
            description="Preventive maintenance visit",
            priority="medium",
            status="open",
            requested_by_id=admin.id,
            due_date=plan.next_due_date,
        ),
    ]
    db.add_all(orders)
    db.add_all(
        [
            Warranty(
                asset_id=asset.id,
                vendor_id=asset.vendor_id,
                start_date=asset.purchase_date,
                end_date=asset.purchase_date + timedelta(days=730),
                terms="Limited manufacturer warranty",
            )
            for asset, _ in assets[:4]
        ]
    )
    db.add(
        Transfer(
            asset_id=assets[0][0].id,
            from_location_id=locations["Mumbai Branch"].id,
            to_location_id=locations["Bengaluru Head Office"].id,
            transferred_by_id=admin.id,
            reason="Sample historical transfer",
            transferred_at=__import__("datetime").datetime.combine(
                today - timedelta(days=200),
                __import__("datetime").time(),
                tzinfo=__import__("datetime").timezone.utc,
            ),
        )
    )
    db.add_all(
        [
            Notification(
                user_id=admin.id,
                title="Welcome to EAMMS",
                message="Your workspace is ready to configure.",
            ),
            Notification(
                user_id=people[1].id,
                title="Work order assigned",
                message="Inspect network switch has been assigned to you.",
            ),
            Notification(
                user_id=people[2].id,
                title="Asset allocated",
                message="A Dell Latitude laptop is assigned to you.",
            ),
        ]
    )


def initialize(db: Session, data: InitialSetupRequest) -> User:
    try:
        if db.bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": LOCK_ID}
            )
        elif db.bind.dialect.name == "sqlite":
            db.connection().exec_driver_sql("BEGIN IMMEDIATE")
        if not setup_required(db):
            raise HTTPException(409, "Initial setup has already been completed")
        normalized_email = str(data.email).strip().lower()
        admin = User(
            full_name=data.full_name,
            email=normalized_email,
            normalized_email=normalized_email,
            password_hash=hash_password(data.password),
            role=Role.ADMINISTRATOR.value,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="user.bootstrap_admin",
                entity_type="user",
                entity_id=str(admin.id),
                details={"source": "first_run_setup"},
            )
        )
        if data.sample_data:
            _sample_data(db, admin)
        db.commit()
        db.refresh(admin)
        return admin
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Initial setup conflicts with existing database records"
        ) from exc
    except Exception:
        db.rollback()
        raise
