from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.db.dependencies import DBSession
from app.models.org_member import MemberRole
from app.models.user import User

bearer_scheme = HTTPBearer()

# ── Current user dependency ──────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    db: DBSession,
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id = UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise credentials_exception

    # Import here to avoid circular import at module level
    from app.crud.user import user_crud

    user = await user_crud.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


# Annotated alias — use this in route signatures instead of Depends() every time
CurrentUser = Annotated[User, Depends(get_current_user)]


# ── RBAC helper ──────────────────────────────────────────────────────────────

_ROLE_HIERARCHY: dict[MemberRole, int] = {
    MemberRole.MEMBER: 0,
    MemberRole.ADMIN: 1,
    MemberRole.OWNER: 2,
}


async def require_org_role(
    user: User,
    org_id: UUID,
    minimum_role: MemberRole,
    db: DBSession,
) -> None:
    """Raise HTTP 403 if user doesn't have minimum_role (or higher) in the org."""
    from app.crud.org_member import org_member_crud

    member = await org_member_crud.get_by_user_and_org(
        db, user_id=user.id, org_id=org_id
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this organization",
        )
    if _ROLE_HIERARCHY[member.role] < _ROLE_HIERARCHY[minimum_role]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {minimum_role} role or higher",
        )
