from fastapi import APIRouter

from app.api.v1 import (
    assets,
    auth,
    departments,
    maintenance,
    reports,
    setup,
    users,
    vendors,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(setup.router)
router.include_router(users.router)
router.include_router(departments.router)
router.include_router(assets.router)
router.include_router(vendors.router)
router.include_router(maintenance.router)
router.include_router(reports.router)
