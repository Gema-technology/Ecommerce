from decimal import Decimal
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.inventory.models import Inventory
from app.modules.orders.models import Order
from app.modules.payments.models import Payment, PaymentStatus
from app.modules.roles.models import User
from app.modules.sri.models import SriConfig
from tests.test_orders_checkout import _login, _seed_sellable


def test_admin_counter_sale_for_unregistered_customer(
    client: TestClient,
    admin_user: User,
    customer_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CTR-OK", price="25.00", stock=5)
    _login(client, admin_user)

    response = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={
            "customer_id": str(customer_user.id),
            "items": [{"product_id": product["id"], "quantity": 2}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PAID"
    assert body["channel"] == "COUNTER"
    assert body["customer_email"] == customer_user.email
    assert body["shipping_total"] == "0.0000"
    assert body["items"][0]["quantity"] == 2

    order = db_session.get(Order, UUID(body["id"]))
    assert order is not None
    db_session.refresh(order)
    assert order.user_id == customer_user.id
    assert order.channel == "COUNTER"

    db_session.expire_all()
    inventory = db_session.scalar(
        select(Inventory).where(Inventory.product_id == UUID(product["id"]))
    )
    assert inventory is not None
    assert inventory.quantity == 3
    assert inventory.reserved_quantity == 0

    payment = db_session.scalar(select(Payment).where(Payment.order_id == order.id))
    assert payment is not None
    assert payment.status == PaymentStatus.SUCCEEDED.value
    assert payment.method == "CASH"

    blocked = client.delete(f"/api/v1/admin/customers/{customer_user.id}")
    assert blocked.status_code == 409

    _login(client, customer_user)
    denied = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={
            "customer_id": str(customer_user.id),
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    assert denied.status_code == 403
    listed = client.get("/api/v1/orders")
    assert listed.status_code == 200
    assert any(item["id"] == body["id"] for item in listed.json()["items"])


def test_counter_sale_without_account(
    client: TestClient,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CTR-WALK", price="12.00", stock=4)
    _login(client, admin_user)
    before_users = db_session.scalar(select(func.count()).select_from(User))

    response = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={
            "customer_name": "  Cliente de paso  ",
            "customer_phone": "0991112233",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "PAID"
    assert body["channel"] == "COUNTER"
    assert body["customer_name"] == "Cliente de paso"
    assert body["customer_phone"] == "0991112233"
    assert body["customer_email"] is None

    order = db_session.get(Order, UUID(body["id"]))
    assert order is not None
    db_session.refresh(order)
    assert order.user_id is None

    db_session.expire_all()
    after_users = db_session.scalar(select(func.count()).select_from(User))
    assert after_users == before_users
    inventory = db_session.scalar(
        select(Inventory).where(Inventory.product_id == UUID(product["id"]))
    )
    assert inventory is not None
    assert inventory.quantity == 3


def test_counter_sale_keeps_buyer_id_for_the_receipt(
    client: TestClient,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CTR-ID", price="8.00", stock=2)
    _login(client, admin_user)
    response = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={
            "customer_name": "Ana Vega",
            "customer_phone": "0998887766",
            "buyer_id_type": "CEDULA",
            "buyer_id_number": "1710034065",
            "address_line": "Av. Mariano Acosta 12-34",
            "city": "Ibarra",
            "province": "Imbabura",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["buyer_id_type"] == "CEDULA"
    assert body["buyer_id_number"] == "1710034065"
    order = db_session.get(Order, UUID(body["id"]))
    assert order is not None
    assert order.buyer_id_type == "CEDULA"
    assert order.buyer_id_number == "1710034065"
    assert order.shipping_address["city"] == "Ibarra"
    assert order.shipping_address["address_line"] == "Av. Mariano Acosta 12-34"

    missing = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={
            "buyer_id_type": "RUC",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
    )
    assert missing.status_code == 422


def test_counter_sale_rejects_insufficient_stock(
    client: TestClient,
    admin_user: User,
    customer_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CTR-LOW", price="10.00", stock=1)
    _login(client, admin_user)
    before = db_session.scalar(select(func.count()).select_from(Order))

    response = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={
            "customer_id": str(customer_user.id),
            "items": [{"product_id": product["id"], "quantity": 4}],
        },
    )
    assert response.status_code == 409, response.text
    db_session.expire_all()
    after = db_session.scalar(select(func.count()).select_from(Order))
    assert after == before
    inventory = db_session.scalar(
        select(Inventory).where(Inventory.product_id == UUID(product["id"]))
    )
    assert inventory is not None
    assert inventory.quantity == 1


def test_counter_sale_preview_shows_totals_without_saving(
    client: TestClient,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CTR-PREV", price="25.00", stock=5)
    _login(client, admin_user)
    before = db_session.scalar(select(func.count()).select_from(Order))

    response = client.post(
        "/api/v1/admin/orders/counter-sale/preview",
        json={"items": [{"product_id": product["id"], "quantity": 2}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert Decimal(body["subtotal"]) == Decimal("50.0000")
    assert Decimal(body["shipping_total"]) == Decimal("0")
    assert Decimal(body["total"]) == (
        Decimal(body["subtotal"])
        - Decimal(body["discount_total"])
        + Decimal(body["tax_total"])
    )
    assert body["items"][0]["quantity"] == 2
    assert Decimal(body["items"][0]["line_total"]) == Decimal("50.0000")

    db_session.expire_all()
    after = db_session.scalar(select(func.count()).select_from(Order))
    assert after == before
    inventory = db_session.scalar(
        select(Inventory).where(Inventory.product_id == UUID(product["id"]))
    )
    assert inventory is not None
    assert inventory.quantity == 5


def test_admin_removes_iva_saved_on_a_negocio_popular_order(
    client: TestClient,
    admin_user: User,
    db_session: Session,
) -> None:
    product = _seed_sellable(client, admin_user, sku="CTR-IVA", price="40.00", stock=3)
    _login(client, admin_user)
    created = client.post(
        "/api/v1/admin/orders/counter-sale",
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
    )
    assert created.status_code == 201, created.text
    order_id = UUID(created.json()["id"])
    order = db_session.get(Order, order_id)
    assert order is not None
    order.tax_total = Decimal("6.0000")
    order.total = Decimal("46.0000")
    payment = db_session.scalar(select(Payment).where(Payment.order_id == order.id))
    assert payment is not None
    payment.amount = Decimal("46.0000")
    db_session.merge(
        SriConfig(
            id=1,
            tax_regime="RIMPE_NEGOCIO_POPULAR",
        )
    )
    db_session.commit()

    removed = client.post(f"/api/v1/admin/orders/{order_id}/remove-iva")
    assert removed.status_code == 200, removed.text
    body = removed.json()
    assert Decimal(body["tax_total"]) == Decimal("0")
    assert Decimal(body["total"]) == Decimal("40.0000")

    db_session.expire_all()
    payment = db_session.scalar(select(Payment).where(Payment.order_id == order_id))
    assert payment is not None
    assert Decimal(payment.amount) == Decimal("40.0000")

    again = client.post(f"/api/v1/admin/orders/{order_id}/remove-iva")
    assert again.status_code == 409
