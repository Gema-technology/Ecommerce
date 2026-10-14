"""PostgreSQL integration checks for reservation expiry concurrency.

Skipped automatically when Postgres is unreachable. Uses an isolated product
SKU prefix and cleans up created rows. Does not rely on SQLite lock semantics.
"""

from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.modules.catalog.models import Product
from app.modules.inventory.models import (
    Inventory,
    InventoryReservation,
    Location,
    ReservationStatus,
)
from app.modules.inventory.service import InventoryService
from app.modules.orders.models import Order, OrderItem, OrderStatus
from app.modules.roles.models import User

_SKU_PREFIX = "PG-EXP-"
_LOCK_KEY = 742_653_601


def _postgres_url() -> str:
    return os.environ.get("DATABASE_URL") or settings.database_url


def _postgres_available() -> bool:
    try:
        engine = create_engine(_postgres_url(), pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:  # noqa: BLE001 — probe only
        return False


pytestmark = pytest.mark.skipif(
    not _postgres_available(),
    reason="PostgreSQL not reachable (set DATABASE_URL or POSTGRES_* / .env)",
)


@pytest.fixture()
def pg_engine():
    engine = create_engine(_postgres_url(), pool_pre_ping=True, pool_size=5)
    yield engine
    engine.dispose()


@pytest.fixture()
def SessionLocal(pg_engine):
    return sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)


def _cleanup(session: Session, product_id: uuid.UUID, order_id: uuid.UUID) -> None:
    session.execute(
        text(
            "DELETE FROM inventory_movements WHERE inventory_id IN "
            "(SELECT id FROM inventory WHERE product_id = :pid)"
        ),
        {"pid": product_id},
    )
    session.execute(
        text("DELETE FROM inventory_reservations WHERE order_id = :oid"),
        {"oid": order_id},
    )
    session.execute(text("DELETE FROM order_items WHERE order_id = :oid"), {"oid": order_id})
    session.execute(text("DELETE FROM orders WHERE id = :oid"), {"oid": order_id})
    session.execute(text("DELETE FROM inventory WHERE product_id = :pid"), {"pid": product_id})
    session.execute(text("DELETE FROM products WHERE id = :pid"), {"pid": product_id})
    session.commit()


def _fence_other_due_actives(session: Session) -> list[tuple[uuid.UUID, datetime]]:
    """Temporarily push unrelated due ACTIVE rows into the future so probes are isolated."""
    rows = list(
        session.execute(
            text(
                "SELECT id, expires_at FROM inventory_reservations "
                "WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at <= NOW() "
                "FOR UPDATE"
            )
        ).all()
    )
    saved: list[tuple[uuid.UUID, datetime]] = [(row[0], row[1]) for row in rows]
    if saved:
        session.execute(
            text(
                "UPDATE inventory_reservations "
                "SET expires_at = NOW() + interval '30 days' "
                "WHERE status = 'ACTIVE' AND expires_at IS NOT NULL AND expires_at <= NOW()"
            )
        )
        session.commit()
    return saved


def _restore_fenced(session: Session, saved: list[tuple[uuid.UUID, datetime]]) -> None:
    for reservation_id, expires_at in saved:
        session.execute(
            text(
                "UPDATE inventory_reservations SET expires_at = :exp WHERE id = :id"
            ),
            {"exp": expires_at, "id": reservation_id},
        )
    if saved:
        session.commit()


def _seed_due_reservation(session: Session) -> tuple[uuid.UUID, uuid.UUID, int]:
    """Create product + inventory hold + PENDING_PAYMENT order due for expiry."""
    user = session.scalar(select(User).limit(1))
    location = session.scalar(select(Location).limit(1))
    donor = session.scalar(select(Product).limit(1))
    assert user is not None, "need at least one user in Postgres"
    assert location is not None, "need at least one location in Postgres"
    assert donor is not None, "need at least one product (for brand/category FKs)"

    sku = f"{_SKU_PREFIX}{uuid.uuid4().hex[:10]}"
    product = Product(
        sku=sku,
        name=f"PG expire probe {sku}",
        slug=f"pg-expire-{uuid.uuid4().hex[:12]}",
        brand_id=donor.brand_id,
        category_id=donor.category_id,
        is_active=True,
    )
    session.add(product)
    session.flush()

    stock = 10
    reserved = 3
    inventory = Inventory(
        product_id=product.id,
        location_id=location.id,
        quantity=stock,
        reserved_quantity=reserved,
    )
    session.add(inventory)
    session.flush()

    order = Order(
        user_id=user.id,
        order_number=f"PGEXP-{uuid.uuid4().hex[:12].upper()}",
        status=OrderStatus.PENDING_PAYMENT.value,
        currency="USD",
        subtotal=Decimal("30.00"),
        tax_total=Decimal("0"),
        shipping_total=Decimal("0"),
        discount_total=Decimal("0"),
        total=Decimal("30.00"),
        customer_email=user.email,
    )
    session.add(order)
    session.flush()
    session.add(
        OrderItem(
            order_id=order.id,
            product_id=product.id,
            product_name_snapshot=product.name,
            sku_snapshot=sku,
            quantity=reserved,
            unit_price=Decimal("10.00"),
            line_total=Decimal("30.00"),
        )
    )
    session.add(
        InventoryReservation(
            inventory_id=inventory.id,
            order_id=order.id,
            quantity=reserved,
            status=ReservationStatus.ACTIVE.value,
            expires_at=datetime.now(UTC) - timedelta(minutes=2),
        )
    )
    session.commit()
    return product.id, order.id, stock


def test_pg_advisory_lock_serializes_overlapping_holders(SessionLocal) -> None:
    """Second connection blocks on pg_advisory_xact_lock until the first commits."""
    acquired_second = threading.Event()
    release_first = threading.Event()
    order: list[str] = []
    errors: list[BaseException] = []

    def holder_a() -> None:
        session = SessionLocal()
        try:
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})
            order.append("a_acquired")
            release_first.wait(timeout=10)
            session.commit()
            order.append("a_released")
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    def holder_b() -> None:
        # Give A a head start so B must wait on the advisory lock.
        threading.Event().wait(0.2)
        session = SessionLocal()
        try:
            session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _LOCK_KEY})
            order.append("b_acquired")
            acquired_second.set()
            session.commit()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)
            session.rollback()
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(holder_a)
        fb = pool.submit(holder_b)
        # B must still be blocked while A holds the lock.
        assert not acquired_second.wait(timeout=1.0), "B acquired lock while A still held it"
        release_first.set()
        fa.result(timeout=15)
        fb.result(timeout=15)

    assert not errors, errors
    assert "a_acquired" in order and "b_acquired" in order
    assert order.index("a_acquired") < order.index("b_acquired")


def test_pg_concurrent_expire_does_not_double_release(SessionLocal) -> None:
    fence = SessionLocal()
    fenced: list[tuple[uuid.UUID, datetime]] = []
    try:
        fenced = _fence_other_due_actives(fence)
        product_id, order_id, stock = _seed_due_reservation(fence)
    finally:
        fence.close()

    barrier = threading.Barrier(2)
    outcomes: list[dict[str, int]] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker() -> None:
        session = SessionLocal()
        try:
            barrier.wait(timeout=10)
            result = InventoryService(session).expire_due_reservations(commit=True)
            with lock:
                outcomes.append(result)
        except BaseException as exc:  # noqa: BLE001
            session.rollback()
            with lock:
                errors.append(exc)
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker), pool.submit(worker)]
            for future in futures:
                future.result(timeout=60)

        assert not errors, errors
        assert sum(item["expired_reservations"] for item in outcomes) == 1
        assert sum(item["cancelled_orders"] for item in outcomes) == 1
        assert sorted(item["expired_reservations"] for item in outcomes) == [0, 1]

        verify = SessionLocal()
        try:
            inv = verify.scalar(select(Inventory).where(Inventory.product_id == product_id))
            assert inv is not None
            assert inv.quantity == stock
            assert inv.reserved_quantity == 0
            reservation = verify.scalar(
                select(InventoryReservation).where(InventoryReservation.order_id == order_id)
            )
            assert reservation is not None
            assert reservation.status == ReservationStatus.EXPIRED.value
            order = verify.get(Order, order_id)
            assert order is not None
            assert order.status == OrderStatus.CANCELLED.value
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal()
        try:
            _cleanup(cleanup, product_id, order_id)
            _restore_fenced(cleanup, fenced)
        finally:
            cleanup.close()


def test_pg_expire_idempotent_second_pass(SessionLocal) -> None:
    fence = SessionLocal()
    fenced: list[tuple[uuid.UUID, datetime]] = []
    try:
        fenced = _fence_other_due_actives(fence)
        product_id, order_id, stock = _seed_due_reservation(fence)
    finally:
        fence.close()

    try:
        first = SessionLocal()
        try:
            r1 = InventoryService(first).expire_due_reservations(commit=True)
        finally:
            first.close()
        second = SessionLocal()
        try:
            r2 = InventoryService(second).expire_due_reservations(commit=True)
        finally:
            second.close()

        assert r1["expired_reservations"] == 1
        assert r1["cancelled_orders"] == 1
        assert r2["expired_reservations"] == 0
        assert r2["cancelled_orders"] == 0

        verify = SessionLocal()
        try:
            inv = verify.scalar(select(Inventory).where(Inventory.product_id == product_id))
            assert inv is not None
            assert inv.quantity == stock
            assert inv.reserved_quantity == 0
        finally:
            verify.close()
    finally:
        cleanup = SessionLocal()
        try:
            _cleanup(cleanup, product_id, order_id)
            _restore_fenced(cleanup, fenced)
        finally:
            cleanup.close()
