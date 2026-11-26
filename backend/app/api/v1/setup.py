from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth import UserOutput
from app.schemas.setup import InitialSetupRequest, InitialSetupResponse, SetupStatus
from app.services.setup import initialize, setup_required

router = APIRouter(prefix="/setup", tags=["first-run setup"])


@router.get("/status", response_model=SetupStatus)
def status(db: Session = Depends(get_db)):
    return SetupStatus(setup_required=setup_required(db))


@router.post("/initial-admin", response_model=InitialSetupResponse, status_code=201)
def create_initial_admin(data: InitialSetupRequest, db: Session = Depends(get_db)):
    user = initialize(db, data)
    return InitialSetupResponse(
        setup_complete=True,
        sample_data_created=data.sample_data,
        administrator=UserOutput.model_validate(user),
    )
