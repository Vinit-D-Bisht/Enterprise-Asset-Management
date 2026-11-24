import logging
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.database.session import SessionLocal
from app.models import MaintenancePlan, Notification, Role, User, Warranty

logger = logging.getLogger("eamms.notifications")
HEARTBEAT_FILE = Path("/tmp/eamms-notifications.last-success")


def deliver_due_notifications(today: date | None = None) -> int:
    today = today or datetime.now(timezone.utc).date()
    reminder_end = today + timedelta(days=30)
    created = 0
    with SessionLocal() as db:
        recipients = db.scalars(
            select(User).where(
                User.is_active.is_(True),
                User.role.in_([Role.ADMINISTRATOR.value, Role.ASSET_MANAGER.value]),
            )
        ).all()
        plans = db.scalars(
            select(MaintenancePlan).where(
                MaintenancePlan.is_active.is_(True),
                MaintenancePlan.next_due_date <= reminder_end,
            )
        ).all()
        warranties = db.scalars(
            select(Warranty).where(
                Warranty.end_date >= today, Warranty.end_date <= reminder_end
            )
        ).all()
        for recipient in recipients:
            for plan in plans:
                key = f"maintenance:{plan.id}:{plan.next_due_date}:{recipient.id}"
                if (
                    db.scalar(
                        select(Notification.id).where(Notification.dedupe_key == key)
                    )
                    is None
                ):
                    db.add(
                        Notification(
                            user_id=recipient.id,
                            title="Preventive maintenance due",
                            message=f"{plan.name} is due for asset {plan.asset_id} on {plan.next_due_date}.",
                            dedupe_key=key,
                        )
                    )
                    created += 1
            for warranty in warranties:
                key = f"warranty:{warranty.id}:{warranty.end_date}:{recipient.id}"
                if (
                    db.scalar(
                        select(Notification.id).where(Notification.dedupe_key == key)
                    )
                    is None
                ):
                    db.add(
                        Notification(
                            user_id=recipient.id,
                            title="Warranty expiration approaching",
                            message=f"Warranty for asset {warranty.asset_id} expires on {warranty.end_date}.",
                            dedupe_key=key,
                        )
                    )
                    created += 1
        if created:
            db.commit()
    return created


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    logger.info("Notification scheduler started")
    while True:
        try:
            created = deliver_due_notifications()
            HEARTBEAT_FILE.touch()
            logger.info("Notification run complete; created=%d", created)
            time.sleep(24 * 60 * 60)
        except Exception:
            logger.exception("Notification run failed")
            time.sleep(60)


if __name__ == "__main__":
    main()
