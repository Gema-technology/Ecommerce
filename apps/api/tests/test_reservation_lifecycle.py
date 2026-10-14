from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.inventory.models import (
    Inventory,
    InventoryMovement,
    InventoryReservation,
    MovementType,
    ReservationStatus,
)
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import PaymentStatus
from app.modules.roles.models import User
from tests.conftest import admin_confirm_payment
from tests.test_orders_checkout import _add_to_cart, _checkout_body, _login, _seed_sellable
from tests.test_payments import _checkout_order


def test_checkout_creates_active_reservation(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-CREATE", stock=5)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])

    reservations = list(
        db_session.scalars(
            select(InventoryReservation).where(InventoryReservation.order_id == order_id)
        ).all()
    )
    assert len(reservations) == 1
    assert reservations[0].status == ReservationStatus.ACTIVE.value
    assert reservations[0].expires_at is not None

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 5
    assert inv.reserved_quantity == 1


def test_payment_success_consumes_reservation(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-OK", qty=2, stock=6)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert (
        admin_confirm_payment(client, admin_user, payment["id"]).status_code
        == 200
    )

    db_session.expire_all()
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.CONSUMED.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 4
    assert inv.reserved_quantity == 0


def test_payment_failure_releases_reservation(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-FAIL", stock=4)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    fail = admin_confirm_payment(client, admin_user, payment["id"], success=False)
    assert fail.status_code == 200
    assert fail.json()["status"] == PaymentStatus.FAILED.value

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PENDING_PAYMENT.value

    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.RELEASED.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 4
    assert inv.reserved_quantity == 0

    release_moves = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_type == "order",
                InventoryMovement.reference_id == str(order_id),
                InventoryMovement.type == MovementType.RELEASE.value,
            )
        ).all()
    )
    assert len(release_moves) == 1


def test_double_release_is_idempotent(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-DBL-REL", stock=3)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)

    first = InventoryService(db_session).release_for_order(
        order_id,
        customer_user,
        terminal_status=ReservationStatus.RELEASED,
        commit=True,
    )
    assert len(first) == 1

    second = InventoryService(db_session).release_for_order(
        order_id,
        customer_user,
        terminal_status=ReservationStatus.RELEASED,
        commit=True,
    )
    assert second == []

    db_session.expire_all()
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0
    release_count = len(
        list(
            db_session.scalars(
                select(InventoryMovement).where(
                    InventoryMovement.reference_id == str(order_id),
                    InventoryMovement.type == MovementType.RELEASE.value,
                )
            ).all()
        )
    )
    assert release_count == 1


def test_double_consume_is_idempotent(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-DBL-CON", stock=5)
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert (
        admin_confirm_payment(client, admin_user, payment["id"]).status_code
        == 200
    )
    # Second confirm is event-idempotent; consume on already-CONSUMED is a no-op.
    again = InventoryService(db_session).consume_for_order(order_id, customer_user, commit=True)
    assert again == []


def test_cancel_pending_releases_stock(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-CANCEL", stock=4)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)

    cancelled = client.post(f"/api/v1/orders/{order_id}/cancel")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == OrderStatus.CANCELLED.value

    db_session.expire_all()
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.RELEASED.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0

    again = client.post(f"/api/v1/orders/{order_id}/cancel")
    assert again.status_code == 409


def test_cancel_rejects_paid_order(
    client: TestClient,
    customer_user: User,
    admin_user: User,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-CAN-PAID")
    order_id = data["order"]["order_id"]
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert (
        admin_confirm_payment(
            client, admin_user, payment["id"], restore_user=customer_user
        ).status_code
        == 200
    )
    assert client.post(f"/api/v1/orders/{order_id}/cancel").status_code == 409


def test_expire_due_reservations_job(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-EXP", stock=3)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])

    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.commit()

    unauthorized = client.post("/api/v1/internal/reservations/expire")
    assert unauthorized.status_code == 401

    wrong_secret = client.post(
        "/api/v1/internal/reservations/expire",
        headers={"X-GEMA-Internal-Secret": "not-the-internal-job-secret"},
    )
    assert wrong_secret.status_code == 401

    response = client.post(
        "/api/v1/internal/reservations/expire",
        headers={"X-GEMA-Internal-Secret": settings.internal_job_secret},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expired_reservations"] == 1
    assert body["cancelled_orders"] == 1

    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.CANCELLED.value
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.EXPIRED.value

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0

    release_moves = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_id == str(order_id),
                InventoryMovement.type == MovementType.RELEASE.value,
            )
        ).all()
    )
    assert len(release_moves) == 1

    # Second run is a no-op (idempotent)
    again = client.post(
        "/api/v1/internal/reservations/expire",
        headers={"X-GEMA-Internal-Secret": settings.internal_job_secret},
    )
    assert again.status_code == 200
    assert again.json()["expired_reservations"] == 0
    assert again.json()["cancelled_orders"] == 0

    db_session.expire_all()
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0
    assert inv.quantity == 3
    release_moves = list(
        db_session.scalars(
            select(InventoryMovement).where(
                InventoryMovement.reference_id == str(order_id),
                InventoryMovement.type == MovementType.RELEASE.value,
            )
        ).all()
    )
    assert len(release_moves) == 1


def test_expire_skips_active_unexpired_reservation(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-LIVE", stock=4)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])

    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.expires_at is not None
    expires_at = reservation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    assert expires_at > datetime.now(UTC)

    response = client.post(
        "/api/v1/internal/reservations/expire",
        headers={"X-GEMA-Internal-Secret": settings.internal_job_secret},
    )
    assert response.status_code == 200
    assert response.json()["expired_reservations"] == 0
    assert response.json()["cancelled_orders"] == 0

    db_session.expire_all()
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.ACTIVE.value
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PENDING_PAYMENT.value
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 1
    assert inv.quantity == 4


def test_expire_survives_process_restart(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
    db_engine,
) -> None:
    """Due work is stored in DB (expires_at); a new session/process still expires it."""
    from sqlalchemy.orm import sessionmaker

    data = _checkout_order(client, customer_user, admin_user, sku="RSV-RESTART", stock=3)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])

    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    reservation.expires_at = datetime.now(UTC) - timedelta(minutes=5)
    db_session.commit()

    # Simulate restart: brand-new session on the same DB (no in-memory job state).
    RestartSession = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    fresh = RestartSession()
    try:
        result = InventoryService(fresh).expire_due_reservations(commit=True)
        assert result["expired_reservations"] == 1
        assert result["cancelled_orders"] == 1
        inv = fresh.scalar(select(Inventory).where(Inventory.product_id == product_id))
        assert inv is not None
        assert inv.reserved_quantity == 0
        order = fresh.get(Order, order_id)
        assert order is not None
        assert order.status == OrderStatus.CANCELLED.value
    finally:
        fresh.close()


def test_expire_error_keeps_inventory_consistent(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-EXP-ROLL", stock=3)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])

    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    # Corrupt reserved so release_for_order raises → expire txn must roll back.
    inv.reserved_quantity = 0
    db_session.commit()

    service = InventoryService(db_session)
    try:
        service.expire_due_reservations(commit=True)
        raise AssertionError("expected conflict during expire")
    except Exception:
        db_session.rollback()

    db_session.expire_all()
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.ACTIVE.value
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PENDING_PAYMENT.value
    # On-hand unchanged; reserved left at the corrupted value until a consistent repair.
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.quantity == 3
    assert inv.reserved_quantity == 0


def test_concurrent_expire_does_not_double_release(tmp_path) -> None:
    """Two overlapping expire runs must not double-release the same reservation.

    Uses a file-backed SQLite DB (multi-connection pool). Distinct from the default
    in-memory StaticPool fixture, which is unsafe across threads. No Postgres/Redis.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.database import Base, get_db
    from app.core.rate_limit import reset_auth_rate_limiter_for_tests
    from app.core.sessions import MemorySessionStore, set_session_store
    from app.main import app
    from app.modules.roles.repository import RoleRepository
    from app.modules.roles.schemas import ROLE_ADMIN, ROLE_CUSTOMER
    from tests.conftest import create_user_with_role

    db_path = tmp_path / "expire_concurrent.db"
    engine = create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    store = MemorySessionStore()
    set_session_store(store)
    reset_auth_rate_limiter_for_tests()

    bootstrap = SessionLocal()
    try:
        RoleRepository(bootstrap).ensure_default_roles()
        bootstrap.commit()
        admin = create_user_with_role(
            bootstrap,
            email="expire-conc-admin@example.com",
            password="secure-password",
            role_name=ROLE_ADMIN,
        )
        customer = create_user_with_role(
            bootstrap,
            email="expire-conc-customer@example.com",
            password="secure-password",
            role_name=ROLE_CUSTOMER,
        )
        # Detach-safe copies for login helpers after bootstrap session closes.
        from types import SimpleNamespace

        admin_ref = SimpleNamespace(id=admin.id, email=admin.email)
        customer_ref = SimpleNamespace(id=customer.id, email=customer.email)
    finally:
        bootstrap.close()

    admin = admin_ref  # type: ignore[assignment]
    customer = customer_ref  # type: ignore[assignment]

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            data = _checkout_order(
                client, customer, admin, sku="RSV-CONC-EXP", stock=5, qty=2
            )
            order_id = UUID(data["order"]["order_id"])
            product_id = UUID(data["product"]["id"])

            setup = SessionLocal()
            try:
                reservation = setup.scalar(
                    select(InventoryReservation).where(
                        InventoryReservation.order_id == order_id
                    )
                )
                assert reservation is not None
                reservation.expires_at = datetime.now(UTC) - timedelta(minutes=1)
                setup.commit()
            finally:
                setup.close()

            barrier = threading.Barrier(2)
            outcomes: list[dict[str, int]] = []
            errors: list[BaseException] = []
            lock = threading.Lock()

            def _worker() -> None:
                session = SessionLocal()
                try:
                    barrier.wait(timeout=5)
                    result = InventoryService(session).expire_due_reservations(commit=True)
                    with lock:
                        outcomes.append(result)
                except BaseException as exc:  # noqa: BLE001 — collect for assertion
                    session.rollback()
                    with lock:
                        errors.append(exc)
                finally:
                    session.close()

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(_worker), pool.submit(_worker)]
                for future in futures:
                    future.result(timeout=30)

            assert not errors, errors
            assert sum(item["expired_reservations"] for item in outcomes) == 1
            assert sum(item["cancelled_orders"] for item in outcomes) == 1

            verify = SessionLocal()
            try:
                inv = verify.scalar(
                    select(Inventory).where(Inventory.product_id == product_id)
                )
                assert inv is not None
                assert inv.quantity == 5
                assert inv.reserved_quantity == 0
                reservation = verify.scalar(
                    select(InventoryReservation).where(
                        InventoryReservation.order_id == order_id
                    )
                )
                assert reservation is not None
                assert reservation.status == ReservationStatus.EXPIRED.value
                releases = list(
                    verify.scalars(
                        select(InventoryMovement).where(
                            InventoryMovement.reference_id == str(order_id),
                            InventoryMovement.type == MovementType.RELEASE.value,
                        )
                    ).all()
                )
                assert len(releases) == 1
            finally:
                verify.close()
    finally:
        app.dependency_overrides.clear()
        set_session_store(MemorySessionStore())
        engine.dispose()


def test_expire_skips_paid_orders(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-EXP-PAID", stock=2)
    order_id = UUID(data["order"]["order_id"])
    _login(client, customer_user)
    payment = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert (
        admin_confirm_payment(client, admin_user, payment["id"]).status_code
        == 200
    )

    # Force an impossible ACTIVE+past expiry state should still be skipped for PAID
    # (consume already set CONSUMED — expire finds nothing).
    result = InventoryService(db_session).expire_due_reservations(commit=True)
    assert result["expired_reservations"] == 0


def test_payment_retry_rereserves_after_failure(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-RETRY", stock=5)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])
    _login(client, customer_user)

    p1 = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    assert (
        admin_confirm_payment(
            client, admin_user, p1["id"], success=False, restore_user=customer_user
        ).status_code
        == 200
    )

    db_session.expire_all()
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 0

    p2 = client.post(f"/api/v1/orders/{order_id}/payment", json={}).json()
    db_session.expire_all()
    active = list(
        db_session.scalars(
            select(InventoryReservation).where(
                InventoryReservation.order_id == order_id,
                InventoryReservation.status == ReservationStatus.ACTIVE.value,
            )
        ).all()
    )
    assert len(active) == 1
    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    assert inv.reserved_quantity == 1

    assert (
        admin_confirm_payment(client, admin_user, p2["id"]).status_code
        == 200
    )
    db_session.expire_all()
    order = db_session.get(Order, order_id)
    assert order is not None
    assert order.status == OrderStatus.PAID.value


def test_release_rollback_on_error(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    data = _checkout_order(client, customer_user, admin_user, sku="RSV-ROLL", stock=3)
    order_id = UUID(data["order"]["order_id"])
    product_id = UUID(data["product"]["id"])

    inv = db_session.scalar(select(Inventory).where(Inventory.product_id == product_id))
    assert inv is not None
    # Corrupt reserved_quantity so release fails integrity check → transaction rolls back.
    inv.reserved_quantity = 0
    db_session.commit()

    service = InventoryService(db_session)
    try:
        service.release_for_order(
            order_id,
            customer_user,
            terminal_status=ReservationStatus.RELEASED,
            commit=True,
        )
        raise AssertionError("expected conflict")
    except Exception:
        db_session.rollback()

    db_session.expire_all()
    reservation = db_session.scalar(
        select(InventoryReservation).where(InventoryReservation.order_id == order_id)
    )
    assert reservation is not None
    assert reservation.status == ReservationStatus.ACTIVE.value


def test_sequential_oversell_still_blocked(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="RSV-OVER", price="10.00", stock=1)
    other = customer_user
    _login(client, other)
    _add_to_cart(client, other, product["id"], 1)
    assert client.post("/api/v1/checkout", json=_checkout_body()).status_code == 200

    from app.modules.roles.schemas import ROLE_CUSTOMER
    from tests.conftest import create_user_with_role

    second = create_user_with_role(
        db_session,
        email="rsv-over-2@example.com",
        password="secure-password",
        role_name=ROLE_CUSTOMER,
    )
    _login(client, second)
    _add_to_cart(client, second, product["id"], 1)
    blocked = client.post("/api/v1/checkout", json=_checkout_body())
    assert blocked.status_code == 409
