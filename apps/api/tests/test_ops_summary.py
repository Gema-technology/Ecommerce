"""Admin ops dashboard summary aggregates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.catalog.models import Brand, Category, Product
from app.modules.inventory.models import (
    Inventory,
    InventoryReservation,
    Location,
    ReservationStatus,
)
from app.modules.notifications.models import NotificationDispatch
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment, PaymentMethod, PaymentStatus
from app.modules.quotes.models import Quote, QuoteStatus
from app.modules.roles.models import User
from app.modules.sri.models import FiscalDocStatus, FiscalDocType, FiscalDocument
from tests.conftest import login_as


def _make_order(
    db: Session,
    user: User,
    *,
    number: str,
    status: str,
    total: str = "100.00",
    created_at: datetime | None = None,
) -> Order:
    order = Order(
        user_id=user.id,
        order_number=number,
        status=status,
        currency="USD",
        subtotal=Decimal(total),
        tax_total=Decimal("0"),
        shipping_total=Decimal("0"),
        discount_total=Decimal("0"),
        total=Decimal(total),
        customer_email=user.email,
        customer_name="Test",
    )
    db.add(order)
    db.flush()
    if created_at is not None:
        order.created_at = created_at
    db.commit()
    db.refresh(order)
    return order


def test_ops_summary_requires_admin(client: TestClient, customer_user: User) -> None:
    login_as(client, customer_user)
    res = client.get("/api/v1/admin/ops/summary")
    assert res.status_code == 403


def test_ops_summary_unauthenticated(client: TestClient) -> None:
    res = client.get("/api/v1/admin/ops/summary")
    assert res.status_code in (401, 403)


def test_ops_summary_aggregates(
    client: TestClient,
    customer_user: User,
    admin_user: User,
    db_session: Session,
) -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=2)
    aging = now - timedelta(hours=30)

    paid = _make_order(
        db_session,
        customer_user,
        number="OPS-PAID-001",
        status=OrderStatus.PAID.value,
        total="50.00",
        created_at=old,
    )
    _make_order(
        db_session,
        customer_user,
        number="OPS-PROC-001",
        status=OrderStatus.PROCESSING.value,
        total="75.00",
        created_at=now - timedelta(hours=1),
    )
    _make_order(
        db_session,
        customer_user,
        number="OPS-PEND-OLD",
        status=OrderStatus.PENDING_PAYMENT.value,
        total="20.00",
        created_at=aging,
    )
    _make_order(
        db_session,
        customer_user,
        number="OPS-PEND-NEW",
        status=OrderStatus.PENDING_PAYMENT.value,
        total="10.00",
        created_at=now - timedelta(hours=1),
    )

    payment = Payment(
        order_id=paid.id,
        provider="bank_transfer",
        method=PaymentMethod.BANK_TRANSFER.value,
        status=PaymentStatus.PROCESSING.value,
        amount=Decimal("50.00"),
        currency="USD",
    )
    db_session.add(payment)

    succeeded = Payment(
        order_id=paid.id,
        provider="manual",
        method=PaymentMethod.CARD.value,
        status=PaymentStatus.SUCCEEDED.value,
        amount=Decimal("50.00"),
        currency="USD",
        paid_at=now - timedelta(hours=2),
    )
    db_session.add(succeeded)

    brand = Brand(name="Ops Brand", slug=f"ops-brand-{uuid4().hex[:8]}")
    category = Category(name="Ops Cat", slug=f"ops-cat-{uuid4().hex[:8]}")
    db_session.add_all([brand, category])
    db_session.flush()
    product = Product(
        name="Ops Product",
        slug=f"ops-product-{uuid4().hex[:8]}",
        sku=f"OPS-{uuid4().hex[:6].upper()}",
        brand_id=brand.id,
        category_id=category.id,
        is_active=True,
    )
    db_session.add(product)
    db_session.flush()
    location = Location(
        name="Ops Warehouse",
        code=f"OPS-{uuid4().hex[:4].upper()}",
        is_active=True,
    )
    db_session.add(location)
    db_session.flush()
    inventory = Inventory(
        product_id=product.id,
        location_id=location.id,
        quantity=2,
        reserved_quantity=0,
        reorder_point=5,
        reorder_quantity=10,
    )
    db_session.add(inventory)
    db_session.flush()

    reservation = InventoryReservation(
        inventory_id=inventory.id,
        order_id=paid.id,
        quantity=1,
        status=ReservationStatus.ACTIVE.value,
        expires_at=now - timedelta(hours=1),
    )
    db_session.add(reservation)

    fiscal = FiscalDocument(
        order_id=paid.id,
        doc_type=FiscalDocType.FACTURA.value,
        status=FiscalDocStatus.REJECTED.value,
        establishment="001",
        emission_point="001",
        sequential=1,
        document_number="001-001-000000001",
        buyer_id_type="CEDULA",
        buyer_id_number="1710034065",
        buyer_name="Test Buyer",
        currency="USD",
        subtotal=Decimal("50"),
        tax_total=Decimal("0"),
        total=Decimal("50"),
        tax_rate=Decimal("0"),
    )
    db_session.add(fiscal)

    dispatch = NotificationDispatch(
        order_id=paid.id,
        event_key="order.paid",
        channel="email",
        status="failed",
        detail="smtp error",
        recipient=customer_user.email,
    )
    db_session.add(dispatch)

    quote = Quote(
        number=f"PRO-{uuid4().hex[:4].upper()}",
        client_name="Cliente Ops",
        status=QuoteStatus.DRAFT.value,
        subtotal=Decimal("100"),
        iva_amount=Decimal("15"),
        total=Decimal("115"),
    )
    db_session.add(quote)
    db_session.commit()

    login_as(client, admin_user)
    res = client.get("/api/v1/admin/ops/summary", params={"period": "7d"})
    assert res.status_code == 200, res.text
    body = res.json()

    kpis = body["kpis"]
    assert kpis["period"] == "7d"
    assert kpis["orders_created"] >= 4
    assert kpis["orders_paid"] >= 2
    assert Decimal(kpis["revenue_succeeded"]) >= Decimal("50")
    assert kpis["orders_by_status"]["PAID"] >= 1
    assert kpis["orders_by_status"]["PROCESSING"] >= 1
    assert kpis["quotes_open"] >= 1
    assert "orders_created_delta_pct" in kpis
    assert "revenue_succeeded_delta_pct" in kpis

    briefing = body["briefing"]
    assert briefing["headline"]
    assert briefing["detail"]
    assert briefing["tone"] in {"clear", "watch", "urgent"}

    money = body["money_at_risk"]
    assert Decimal(money["awaiting_payment_confirm"]) >= Decimal("50")
    assert Decimal(money["fulfillment_backlog"]) >= Decimal("50")
    assert Decimal(money["total"]) >= Decimal("50")

    work_items = body["work_items"]
    assert len(work_items) >= 3
    kinds = {item["kind"] for item in work_items}
    assert "confirm_payment" in kinds
    assert "fulfill_order" in kinds
    assert work_items[0]["score"] >= work_items[-1]["score"]
    assert work_items[0]["href"].startswith("/admin/")
    assert work_items[0]["action_label"]

    attention_keys = {item["key"]: item for item in body["attention"]}
    assert "offline_payments" in attention_keys
    assert attention_keys["offline_payments"]["severity"] == "high"
    assert attention_keys["offline_payments"]["href"] == "/admin/payments"

    assert "fulfillment_backlog" in attention_keys
    assert attention_keys["fulfillment_backlog"]["count"] >= 2

    assert "aging_pending_payment" in attention_keys
    assert attention_keys["aging_pending_payment"]["count"] >= 1

    assert "fiscal_rejected" in attention_keys
    assert attention_keys["fiscal_rejected"]["severity"] == "critical"

    assert "low_stock" in attention_keys
    assert "expired_reservations" in attention_keys
    assert attention_keys["expired_reservations"]["severity"] == "critical"

    assert "failed_emails" in attention_keys

    assert len(body["recent_orders"]) >= 1
    assert body["recent_orders"][0]["order_number"]


def test_ops_summary_period_today(
    client: TestClient, admin_user: User, customer_user: User, db_session: Session
) -> None:
    _make_order(
        db_session,
        customer_user,
        number="OPS-TODAY-1",
        status=OrderStatus.DELIVERED.value,
        total="33.00",
    )
    login_as(client, admin_user)
    res = client.get("/api/v1/admin/ops/summary", params={"period": "today"})
    assert res.status_code == 200
    assert res.json()["kpis"]["period"] == "today"
