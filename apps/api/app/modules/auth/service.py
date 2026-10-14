from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password
from app.core.sessions import SessionStore, get_session_store
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.roles.models import User
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import ROLE_CUSTOMER
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserPublic
from app.modules.users.service import user_to_public

GENERIC_AUTH_ERROR = "Invalid email or password"


class AuthService:
    def __init__(self, db: Session, session_store: SessionStore | None = None) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.roles = RoleRepository(db)
        self.sessions = session_store or get_session_store()

    def register(self, data: RegisterRequest) -> tuple[UserPublic, str]:
        existing = self.users.get_by_email(data.email)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered",
            )

        customer_role = self.roles.get_by_name(ROLE_CUSTOMER)
        if customer_role is None:
            self.roles.ensure_default_roles()
            customer_role = self.roles.get_by_name(ROLE_CUSTOMER)
        if customer_role is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Default roles are not seeded",
            )

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            is_active=True,
            email_verified=False,
        )
        self.users.create(user)
        self.roles.assign_role(user.id, customer_role)
        self.db.commit()

        user = self.users.get_by_id(user.id)
        assert user is not None

        session_id = self.sessions.create(str(user.id), settings.session_ttl_seconds)
        return user_to_public(user), session_id

    def login(self, data: LoginRequest) -> tuple[UserPublic, str]:
        user = self.users.get_by_email(data.email)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_AUTH_ERROR,
            )
        if not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=GENERIC_AUTH_ERROR,
            )

        session_id = self.sessions.create(str(user.id), settings.session_ttl_seconds)
        return user_to_public(user), session_id

    def logout(self, session_id: str | None) -> None:
        if session_id:
            self.sessions.delete(session_id)

    def get_user_for_session(self, session_id: str | None) -> User | None:
        if not session_id:
            return None
        data = self.sessions.get(session_id)
        if data is None:
            return None
        from uuid import UUID

        try:
            user_id = UUID(data.user_id)
        except ValueError:
            return None
        user = self.users.get_by_id(user_id)
        if user is None or not user.is_active:
            return None
        return user
