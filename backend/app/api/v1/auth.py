from typing import Annotated
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from redis.asyncio import Redis

from app.core.auth_dependencies import CurrentUser
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    verify_password,
)
from app.crud.organization import organization_crud
from app.crud.user import user_crud
from app.db.dependencies import DBSession
from app.db.redis import get_redis
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.common import MessageResponse
from app.schemas.organization import OrgCreate
from app.schemas.user import UserPublic
from app.models.organization import OrgType
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])

# The refresh token lives in an httpOnly cookie that page scripts can't read.
# SameSite=Strict keeps it off cross-site requests, and the path scopes it to
# the auth endpoints so it isn't sent with every API call.
REFRESH_COOKIE = "kuzot_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="strict",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="strict",
    )


async def _issue_tokens(user: User, redis: Redis, response: Response) -> TokenResponse:
    """Create an access token and a fresh single-use refresh token for the user."""
    access_token = create_access_token(user.id, user.email)
    refresh_token, jti = create_refresh_token(user.id)

    # Store jti in Redis with TTL matching refresh token expiration
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh_token:{jti}", ttl_seconds, str(user.id))

    _set_refresh_cookie(response, refresh_token)
    return TokenResponse(access_token=access_token)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: DBSession,
):
    existing = await user_crud.get_by_email(db, body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user = await user_crud.create(db, body)

    # Automatically create a personal organization for the new user
    personal_org_name = f"{user.full_name or user.email}'s Org"
    await organization_crud.create(
        db,
        obj_in=OrgCreate(name=personal_org_name, org_type=OrgType.PERSONAL),
        user_id=user.id,
    )

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
):
    user = await user_crud.get_by_email(db, body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive",
        )

    return await _issue_tokens(user, redis, response)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    db: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
    refresh_token: RefreshCookie = None,
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    try:
        payload = decode_refresh_token(refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        jti = payload["jti"]
        user_id_str = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Single-use rotation: GETDEL reads and invalidates the jti atomically,
    # so two concurrent refreshes with the same token can't both succeed.
    # The client decodes responses, so the stored value is already a str.
    stored_user_id = await redis.getdel(f"refresh_token:{jti}")
    if stored_user_id != user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    user = await user_crud.get_by_id(db, user_id_str)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
        )

    return await _issue_tokens(user, redis, response)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    redis: Annotated[Redis, Depends(get_redis)],
    refresh_token: RefreshCookie = None,
):
    if refresh_token:
        try:
            payload = decode_refresh_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                await redis.delete(f"refresh_token:{jti}")
        except Exception:
            pass  # even if invalid, logout request succeeds gracefully

    _clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: CurrentUser):
    return current_user
