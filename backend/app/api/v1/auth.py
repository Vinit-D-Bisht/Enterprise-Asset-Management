from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.security import create_access_token
from app.database.session import get_db
from app.models import User
from app.schemas.auth import CurrentUserOutput, LoginInput, TokenOutput
from app.services.auth import authenticate, revoke_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["authentication"])
COOKIE_NAME = "eamms_refresh"
COOKIE_PATH = "/api/v1/auth"


def validate_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origin_list:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Untrusted request origin")


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.JWT_REFRESH_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path=COOKIE_PATH,
    )


@router.post("/login", response_model=TokenOutput)
def login(
    data: LoginInput,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    validate_origin(request)
    user, refresh = authenticate(
        db, data, request.client.host if request.client else "unknown"
    )
    set_refresh_cookie(response, refresh)
    return TokenOutput(access_token=create_access_token(user.id))


@router.post("/refresh", response_model=TokenOutput)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    validate_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token required")
    user, replacement = rotate_refresh_token(db, token)
    set_refresh_cookie(response, replacement)
    return TokenOutput(access_token=create_access_token(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    validate_origin(request)
    revoke_refresh_token(db, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(
        COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
    )


@router.get("/me", response_model=CurrentUserOutput)
def me(user: User = Depends(get_current_user)):
    return user
