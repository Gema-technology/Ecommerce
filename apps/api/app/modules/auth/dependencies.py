from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.sessions import get_session_store
from app.modules.auth.service import AuthService
from app.modules.roles.models import User
from app.modules.roles.schemas import ROLE_ADMIN, ROLE_SUPER_ADMIN


def get_auth_service(db: Annotated[Session, Depends(get_db)]) -> AuthService:
    return AuthService(db, get_session_store())


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    session_id: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> User | None:
    return AuthService(db, get_session_store()).get_user_for_session(session_id)


def require_authenticated_user(
    user: Annotated[User | None, Depends(get_current_user)],
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_role(role_name: str) -> Callable[..., User]:
    def dependency(user: Annotated[User, Depends(require_authenticated_user)]) -> User:
        if role_name not in user.role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


def require_any_role(*role_names: str) -> Callable[..., User]:
    allowed = set(role_names)

    def dependency(user: Annotated[User, Depends(require_authenticated_user)]) -> User:
        if not allowed.intersection(user.role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency


RequireAdmin = Annotated[
    User,
    Depends(require_any_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)),
]
RequireSuperAdmin = Annotated[User, Depends(require_role(ROLE_SUPER_ADMIN))]
CurrentUser = Annotated[User, Depends(require_authenticated_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user)]
