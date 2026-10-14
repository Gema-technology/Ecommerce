import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import reset_auth_rate_limiter_for_tests
from app.core.security import hash_password
from app.core.sessions import MemorySessionStore, set_session_store
from app.main import app
from app.modules.roles.models import Role, User, UserRole
from app.modules.roles.repository import RoleRepository
from app.modules.roles.schemas import ROLE_ADMIN, ROLE_CUSTOMER, ROLE_SUPER_ADMIN


@pytest.fixture()
def session_store() -> MemorySessionStore:
    store = MemorySessionStore()
    set_session_store(store)
    yield store
    store.clear()
    set_session_store(MemorySessionStore())


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Session:
    TestingSessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = TestingSessionLocal()
    RoleRepository(session).ensure_default_roles()
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _isolate_payment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests independent of the developer's local .env payment provider."""
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "payment_default_provider", "manual")
    monkeypatch.setattr(config_mod.settings, "app_env", "development")
    monkeypatch.setattr(config_mod.settings, "session_cookie_secure", False)
    monkeypatch.setattr(config_mod.settings, "allow_manual_payment_confirm", None)


@pytest.fixture()
def client(db_session: Session, session_store: MemorySessionStore) -> TestClient:
    reset_auth_rate_limiter_for_tests()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_user_with_role(
    db: Session,
    *,
    email: str,
    password: str,
    role_name: str,
    is_active: bool = True,
) -> User:
    from datetime import UTC, datetime

    from app.modules.employees.models import Employee, EmployeeStatus

    role = db.scalar(select(Role).where(Role.name == role_name))
    assert role is not None
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        first_name="Test",
        last_name="User",
        is_active=is_active,
        email_verified=False,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))
    if role_name in {ROLE_ADMIN, ROLE_SUPER_ADMIN}:
        db.add(
            Employee(
                user_id=user.id,
                status=EmployeeStatus.ACTIVE.value,
                accepted_at=datetime.now(UTC),
            )
        )
    db.commit()
    db.refresh(user)
    return user


def login_as(client: TestClient, user: User, *, password: str = "secure-password") -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )


def admin_confirm_payment(
    client: TestClient,
    admin: User,
    payment_id: str,
    *,
    success: bool = True,
    restore_user: User | None = None,
) -> object:
    login_as(client, admin)
    response = client.post(
        f"/api/v1/admin/payments/{payment_id}/confirm?success={'true' if success else 'false'}"
    )
    client.cookies.clear()
    if restore_user is not None:
        login_as(client, restore_user)
    return response


@pytest.fixture()
def customer_user(db_session: Session) -> User:
    return create_user_with_role(
        db_session,
        email="customer@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )


@pytest.fixture()
def admin_user(db_session: Session) -> User:
    return create_user_with_role(
        db_session,
        email="admin@example.com",
        password="secure-password",
        role_name=ROLE_ADMIN,
    )


@pytest.fixture()
def super_admin_user(db_session: Session) -> User:
    return create_user_with_role(
        db_session,
        email="super@example.com",
        password="secure-password",
        role_name=ROLE_SUPER_ADMIN,
    )
