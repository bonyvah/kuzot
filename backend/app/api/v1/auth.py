from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
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
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.common import MessageResponse
from app.schemas.organization import OrgCreate
from app.schemas.user import UserPublic
from app.models.organization import OrgType

router = APIRouter(prefix="/auth", tags=["Auth"])


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

    access_token = create_access_token(user.id, user.email)
    refresh_token, jti = create_refresh_token(user.id)

    # Store jti in Redis with TTL matching refresh token expiration
    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh_token:{jti}", ttl_seconds, str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    db: DBSession,
    redis: Annotated[Redis, Depends(get_redis)],
):
    try:
        payload = decode_refresh_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise ValueError("Invalid token type")
        jti = payload["jti"]
        user_id_str = payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Check if jti exists in Redis
    redis_key = f"refresh_token:{jti}"
    stored_user_id = await redis.get(redis_key)
    if not stored_user_id or stored_user_id.decode("utf-8") != user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token revoked or expired",
        )

    # Single-use refresh token rotation: invalidate used token
    await redis.delete(redis_key)

    user = await user_crud.get_by_id(db, user_id_str)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User inactive or not found",
        )

    new_access_token = create_access_token(user.id, user.email)
    new_refresh_token, new_jti = create_refresh_token(user.id)

    ttl_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"refresh_token:{new_jti}", ttl_seconds, str(user.id))

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    body: RefreshRequest,
    redis: Annotated[Redis, Depends(get_redis)],
):
    try:
        payload = decode_refresh_token(body.refresh_token)
        jti = payload.get("jti")
        if jti:
            await redis.delete(f"refresh_token:{jti}")
    except Exception:
        pass  # even if invalid, logout request succeeds gracefully

    return MessageResponse(message="Successfully logged out")


@router.get("/me", response_model=UserPublic)
async def get_me(current_user: CurrentUser):
    return current_user
