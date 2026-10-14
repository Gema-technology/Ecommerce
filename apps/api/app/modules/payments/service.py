from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.inventory.models import ReservationStatus
from app.modules.inventory.service import InventoryService
from app.modules.notifications.service import EVENT_ORDER_PAID, notify_order_event
from app.modules.orders.models import Order, OrderStatus, OrderStatusEvent
from app.modules.payments.models import Payment, PaymentEvent, PaymentMethod, PaymentStatus
from app.modules.payments.providers import get_provider, provider_for_method
from app.modules.payments.providers.bank_transfer import (
    BankTransferPaymentProvider,
    bank_details_dict,
)
from app.modules.payments.providers.base import OrderAmountBreakdown, ProviderWebhookResult
from app.modules.payments.providers.payphone import PayPhonePaymentProvider, money_to_cents
from app.modules.payments.repository import PaymentRepository
from app.modules.payments.schemas import (
    PaymentCreateRequest,
    PaymentListResponse,
    PaymentRead,
)
from app.modules.roles.models import User
from app.modules.store_config.service import StoreConfigService


class PaymentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PaymentRepository(db)
        self.inventory = InventoryService(db)

    def _to_read(
        self,
        payment: Payment,
        *,
        client_action: dict | None = None,
    ) -> PaymentRead:
        action = client_action
        if action is None:
            action = self._rebuild_client_action(payment)
        return PaymentRead(
            id=payment.id,
            payment_id=payment.id,
            order_id=payment.order_id,
            order_number=payment.order.order_number if payment.order else None,
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            method=payment.method,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            metadata=payment.metadata_json or {},
            created_at=payment.created_at,
            updated_at=payment.updated_at,
            paid_at=payment.paid_at,
            client_action=action,
        )

    def _rebuild_client_action(self, payment: Payment) -> dict | None:
        meta = payment.metadata_json or {}
        reference = str(
            meta.get("reference")
            or (payment.order.order_number if payment.order else "")
        )
        if payment.provider == "bank_transfer":
            if isinstance(meta.get("bank"), dict):
                bank = meta["bank"]
            else:
                bank = bank_details_dict(StoreConfigService(self.db).get_read())
            return {
                "type": "bank_transfer_instructions",
                "payment_id": str(payment.id),
                "reference": reference,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "bank": bank,
                "hint": (
                    "Realiza la transferencia con el monto exacto y usa el número "
                    "de orden como referencia. Luego pulsa «Ya transferí»."
                ),
                "customer_marked_transferred": bool(meta.get("customer_marked_transferred_at")),
            }
        if payment.provider == "cash_on_delivery":
            return {
                "type": "cash_on_delivery_pending",
                "payment_id": str(payment.id),
                "reference": reference,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "hint": (
                    "Pagarás en efectivo al recibir el pedido. "
                    "Un operador confirmará el cobro al entregar."
                ),
            }
        return None

    def create_for_order(
        self,
        user: User,
        order_id: UUID,
        payload: PaymentCreateRequest,
    ) -> PaymentRead:
        order = self.db.scalar(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
            .with_for_update()
        )
        if order is None or order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        if order.status == OrderStatus.CANCELLED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order is cancelled",
            )
        if order.status == OrderStatus.PAID.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order is already paid",
            )
        if order.status != OrderStatus.PENDING_PAYMENT.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order is not awaiting payment",
            )
        if self.repo.has_succeeded(order.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order already has a successful payment",
            )

        # After payment failure, ACTIVE holds were released — re-acquire before a new attempt.
        self.inventory.ensure_active_holds_for_order(order, user, commit=False)

        if payload.method == PaymentMethod.CASH_ON_DELIVERY:
            if not bool(getattr(user, "allow_cash_on_delivery", False)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "Cash on delivery is only available for trusted customers. "
                        "Contact GEMA to request access."
                    ),
                )

        provider = provider_for_method(payload.method.value)
        payment = Payment(
            order_id=order.id,
            provider=provider.name,
            method=payload.method.value,
            status=PaymentStatus.PENDING.value,
            amount=order.total,
            currency=order.currency or "USD",
            metadata_json={},
        )
        self.repo.add(payment)

        breakdown = OrderAmountBreakdown(
            total=Decimal(str(order.total)),
            subtotal=Decimal(str(order.subtotal)),
            tax_total=Decimal(str(order.tax_total or 0)),
            shipping_total=Decimal(str(order.shipping_total or 0)),
            discount_total=Decimal(str(order.discount_total or 0)),
        )
        create_kwargs: dict = {
            "payment_id": payment.id,
            "order_id": order.id,
            "order_number": order.order_number,
            "amount": str(order.total),
            "currency": payment.currency,
            "method": payment.method,
            "breakdown": breakdown,
        }
        if isinstance(provider, BankTransferPaymentProvider):
            create_kwargs["store_config"] = StoreConfigService(self.db).get_read()
        result = provider.create_payment(**create_kwargs)
        payment.provider_payment_id = result.provider_payment_id
        payment.status = result.status
        payment.metadata_json = result.metadata
        self.db.commit()
        loaded = self.repo.get(payment.id)
        assert loaded is not None
        return self._to_read(loaded, client_action=result.client_action)

    def list_for_order(self, user: User, order_id: UUID) -> list[PaymentRead]:
        order = self.db.get(Order, order_id)
        if order is None or order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return [self._to_read(p) for p in self.repo.list_for_order(order_id)]

    def get_for_user(self, user: User, payment_id: UUID) -> PaymentRead:
        payment = self.repo.get(payment_id)
        if payment is None or payment.order is None or payment.order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return self._to_read(payment)

    def admin_list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        provider: str | None = None,
        q: str | None = None,
    ) -> PaymentListResponse:
        from app.core.pagination import total_pages

        items, total = self.repo.list_all(
            page=page,
            page_size=page_size,
            status=status,
            provider=provider,
            q=q,
        )
        return PaymentListResponse(
            items=[self._to_read(p) for p in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages(total, page_size),
        )

    def admin_get(self, payment_id: UUID) -> PaymentRead:
        payment = self.repo.get(payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return self._to_read(payment)

    def confirm_manual_admin(self, payment_id: UUID, *, success: bool) -> PaymentRead:
        """Admin confirm for offline providers: manual (env-gated) or bank_transfer."""
        from app.core.config import settings

        payment = self.repo.get(payment_id, for_update=True)
        if payment is None or payment.order is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

        if payment.provider == "manual":
            if not settings.manual_payment_confirm_allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Manual payment confirmation is disabled in this environment",
                )
        elif payment.provider in {"bank_transfer", "cash_on_delivery"}:
            pass  # Always allowed — ops verifies deposit / delivery payment
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Confirm is only available for manual, bank_transfer, "
                    "or cash_on_delivery payments"
                ),
            )

        order_user = self.db.get(User, payment.order.user_id)
        if order_user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Order owner missing",
            )
        return self._confirm_offline_payment(
            payment, order_user=order_user, success=success
        )

    def mark_bank_transfer_submitted(self, user: User, payment_id: UUID) -> PaymentRead:
        """Customer acknowledges they sent the wire — does not mark the order paid."""
        payment = self.repo.get(payment_id, for_update=True)
        if payment is None or payment.order is None or payment.order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if payment.provider != "bank_transfer":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only bank transfer payments can be marked as transferred",
            )
        if payment.method != PaymentMethod.BANK_TRANSFER.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment method is not bank transfer",
            )
        if payment.status == PaymentStatus.SUCCEEDED.value:
            return self._to_read(payment)
        if payment.status not in {
            PaymentStatus.PENDING.value,
            PaymentStatus.PROCESSING.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment cannot be marked as transferred in its current state",
            )
        meta = dict(payment.metadata_json or {})
        meta["customer_marked_transferred_at"] = datetime.now(UTC).isoformat()
        payment.metadata_json = meta
        payment.status = PaymentStatus.PROCESSING.value
        self.db.commit()
        loaded = self.repo.get(payment.id)
        assert loaded is not None
        return self._to_read(loaded)

    def _confirm_offline_payment(
        self,
        payment: Payment,
        *,
        order_user: User,
        success: bool,
    ) -> PaymentRead:
        provider_name = payment.provider
        event_id = f"{provider_name}-confirm-{'ok' if success else 'fail'}-{payment.id}"
        if self.repo.get_event(provider_name, event_id) is not None:
            return self._to_read(payment)

        event = PaymentEvent(
            provider=provider_name,
            provider_event_id=event_id,
            event_type="payment.succeeded" if success else "payment.failed",
            payload={"source": "admin_confirm"},
            payment_id=payment.id,
            processed_at=None,
        )
        try:
            self.repo.add_event(event)
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            loaded = self.repo.get(payment.id)
            assert loaded is not None
            return self._to_read(loaded)

        became_paid = False
        try:
            if success:
                became_paid = self._apply_success(payment, user=order_user)
            else:
                self._apply_failure(payment, user=order_user)
            event.processed_at = datetime.now(UTC)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        if became_paid:
            notify_order_event(self.db, payment.order_id, EVENT_ORDER_PAID)
        loaded = self.repo.get(payment.id)
        assert loaded is not None
        return self._to_read(loaded)

    def process_webhook(
        self,
        provider_name: str,
        *,
        headers: dict[str, str],
        body: bytes,
    ) -> dict:
        provider = get_provider(provider_name)
        result = provider.handle_webhook(headers=headers, body=body)
        return self._apply_provider_result(provider.name, result)

    def sync_payment_status(self, user: User, payment_id: UUID) -> PaymentRead:
        """Poll the PSP (PayPhone Sale API) and apply terminal status if available."""
        payment = self.repo.get(payment_id, for_update=True)
        if payment is None or payment.order is None or payment.order.user_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        if payment.status == PaymentStatus.SUCCEEDED.value:
            return self._to_read(payment)
        if payment.provider != "payphone":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Status sync is only available for PayPhone payments",
            )
        if not payment.provider_payment_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment has no PayPhone reference",
            )

        provider = get_provider("payphone")
        assert isinstance(provider, PayPhonePaymentProvider)
        result = provider.sync_from_remote(payment.provider_payment_id)
        # client_tx is hex[:15]; bind the locked payment row explicitly.
        result = replace(result, payment_id=payment.id)
        self._apply_provider_result("payphone", result)
        loaded = self.repo.get(payment.id)
        assert loaded is not None
        return self._to_read(loaded)

    def _apply_provider_result(
        self, provider_name: str, result: ProviderWebhookResult
    ) -> dict:
        existing = self.repo.get_event(provider_name, result.provider_event_id)
        if existing is not None:
            return {"status": "already_processed", "event_id": result.provider_event_id}

        event = PaymentEvent(
            provider=provider_name,
            provider_event_id=result.provider_event_id,
            event_type=result.event_type,
            payload=result.payload,
            payment_id=result.payment_id,
            processed_at=None,
        )
        try:
            self.repo.add_event(event)
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            return {"status": "already_processed", "event_id": result.provider_event_id}

        if result.outcome == "ignored":
            event.processed_at = datetime.now(UTC)
            self.db.commit()
            return {"status": "ignored", "event_id": result.provider_event_id}

        payment = None
        if result.payment_id is not None:
            payment = self.repo.get(result.payment_id, for_update=True)
        if payment is None and result.provider_payment_id:
            payment = self.repo.get_by_provider_payment_id(
                provider_name,
                result.provider_payment_id,
                for_update=True,
            )
        if payment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found",
            )

        if provider_name == "payphone" and result.outcome == "succeeded":
            self._assert_payphone_amount(payment, result.payload)

        if payment.order is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment order missing",
            )
        order_user = self.db.get(User, payment.order.user_id)
        if order_user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Order owner missing",
            )

        became_paid = False
        if result.outcome == "succeeded":
            became_paid = self._apply_success(payment, user=order_user)
        elif result.outcome == "failed":
            self._apply_failure(payment, user=order_user)

        meta = dict(payment.metadata_json or {})
        tx_id = result.payload.get("TransactionId") or result.payload.get("transactionId")
        if tx_id is not None:
            meta["payphone_transaction_id"] = tx_id
        auth = result.payload.get("AuthorizationCode") or result.payload.get(
            "authorizationCode"
        )
        if auth:
            meta["payphone_authorization_code"] = auth
        payment.metadata_json = meta

        event.processed_at = datetime.now(UTC)
        event.payment_id = payment.id
        self.db.commit()
        if became_paid:
            notify_order_event(self.db, payment.order_id, EVENT_ORDER_PAID)
        return {
            "status": "processed",
            "event_id": result.provider_event_id,
            "payment_status": payment.status,
        }

    def _assert_payphone_amount(self, payment: Payment, payload: dict) -> None:
        raw = payload.get("Amount", payload.get("amount"))
        if raw is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="PayPhone amount is required",
            )
        try:
            reported = int(raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PayPhone amount",
            ) from exc
        expected = money_to_cents(Decimal(str(payment.amount)))
        if reported != expected:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="PayPhone amount does not match order payment",
            )

    def _apply_success(self, payment: Payment, *, user: User) -> bool:
        """Mark payment/order paid. Returns True when order newly became PAID."""
        if payment.status == PaymentStatus.SUCCEEDED.value:
            return False
        if payment.status in {
            PaymentStatus.CANCELLED.value,
            PaymentStatus.REFUNDED.value,
        }:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payment cannot transition to succeeded",
            )

        order = self.db.scalar(
            select(Order).where(Order.id == payment.order_id).with_for_update()
        )
        assert order is not None
        if order.status == OrderStatus.PAID.value:
            # Another attempt already paid this order — do not succeed again
            # or re-consume inventory.
            payment.status = PaymentStatus.FAILED.value
            return False
        if order.status != OrderStatus.PENDING_PAYMENT.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order cannot be marked paid",
            )
        if self.repo.has_succeeded(order.id):
            payment.status = PaymentStatus.FAILED.value
            return False

        payment.status = PaymentStatus.SUCCEEDED.value
        payment.paid_at = datetime.now(UTC)
        previous = order.status
        order.status = OrderStatus.PAID.value
        self.db.add(
            OrderStatusEvent(
                order_id=order.id,
                from_status=previous,
                to_status=OrderStatus.PAID.value,
                actor_user_id=None,
                note="Payment confirmed",
            )
        )
        self.inventory.consume_for_order(order.id, user, commit=False)
        self.db.flush()
        return True

    def _apply_failure(self, payment: Payment, *, user: User) -> None:
        if payment.status == PaymentStatus.SUCCEEDED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Successful payment cannot fail",
            )
        payment.status = PaymentStatus.FAILED.value

        order = self.db.scalar(
            select(Order).where(Order.id == payment.order_id).with_for_update()
        )
        if order is not None and order.status == OrderStatus.PENDING_PAYMENT.value:
            self.inventory.release_for_order(
                order.id,
                user,
                terminal_status=ReservationStatus.RELEASED,
                notes="Payment failure — reservation released",
                commit=False,
            )
        self.db.flush()
