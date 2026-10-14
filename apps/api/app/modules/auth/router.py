from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import check_auth_rate_limit
from app.core.sessions import get_session_store
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.schemas import LoginRequest, MessageResponse, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.employees.schemas import AcceptInviteRequest, EmployeeListItem
from app.modules.employees.service import EmployeeService
from app.modules.users.schemas import UserPublic
from app.modules.users.service import user_to_public

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.session_ttl_seconds,
        path="/",
    )


def _client_rate_limit_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,  # type: ignore[arg-type]
    )


@router.post("/register", response_model=UserPublic, status_code=201)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    check_auth_rate_limit(_client_rate_limit_key(request))
    user, session_id = AuthService(db, get_session_store()).register(payload)
    _set_session_cookie(response, session_id)
    return user


@router.post("/login", response_model=UserPublic)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> UserPublic:
    check_auth_rate_limit(_client_rate_limit_key(request))
    user, session_id = AuthService(db, get_session_store()).login(payload)
    _set_session_cookie(response, session_id)
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    session_id: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> MessageResponse:
    AuthService(db, get_session_store()).logout(session_id)
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserPublic)
def me(user: CurrentUser) -> UserPublic:
    return user_to_public(user)


@router.post("/accept-invite", response_model=EmployeeListItem)
def accept_invite(
    payload: AcceptInviteRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> EmployeeListItem:
    check_auth_rate_limit(_client_rate_limit_key(request))
    return EmployeeService(db).accept_invite(payload)
