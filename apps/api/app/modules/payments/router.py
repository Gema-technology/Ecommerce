from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import secrets_equal
from app.modules.auth.dependencies import CurrentUser, RequireAdmin
from app.modules.payments.schemas import (
    PaymentCreateRequest,
    PaymentListResponse,
    PaymentRead,
)
from app.modules.payments.service import PaymentService

router = APIRouter(tags=["payments"])


def get_payment_service(db: Annotated[Session, Depends(get_db)]) -> PaymentService:
    return PaymentService(db)


@router.post("/orders/{order_id}/payment", response_model=PaymentRead)
def create_payment(
    order_id: UUID,
    user: CurrentUser,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    payload: PaymentCreateRequest | None = None,
) -> PaymentRead:
    return service.create_for_order(
        user, order_id, payload or PaymentCreateRequest()
    )


@router.get("/orders/{order_id}/payments", response_model=PaymentListResponse)
def list_order_payments(
    order_id: UUID,
    user: CurrentUser,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentListResponse:
    return PaymentListResponse(items=service.list_for_order(user, order_id))


@router.get("/payments/{payment_id}", response_model=PaymentRead)
def get_payment(
    payment_id: UUID,
    user: CurrentUser,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentRead:
    return service.get_for_user(user, payment_id)


@router.post("/payments/{payment_id}/sync", response_model=PaymentRead)
def sync_payment(
    payment_id: UUID,
    user: CurrentUser,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentRead:
    """Poll PayPhone Sale API and confirm the payment when approved."""
    return service.sync_payment_status(user, payment_id)


@router.post("/payments/{payment_id}/mark-transferred", response_model=PaymentRead)
def mark_bank_transfer_submitted(
    payment_id: UUID,
    user: CurrentUser,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentRead:
    """Customer signals they completed the wire transfer (admin still confirms)."""
    return service.mark_bank_transfer_submitted(user, payment_id)


@router.post("/admin/payments/{payment_id}/confirm", response_model=PaymentRead)
def admin_confirm_payment(
    payment_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    success: bool = True,
) -> PaymentRead:
    """Admin confirm for offline payments (manual env-gated; bank_transfer always)."""
    return service.confirm_manual_admin(payment_id, success=success)


def _verify_payphone_webhook_secret(
    *,
    header_secret: str | None,
    query_token: str | None,
) -> None:
    """Authenticate PayPhone Notificacion Externa via shared secret.

    PayPhone supports a caller-configured token (query ``token`` or header).
    Staging/production fail closed when ``PAYPHONE_WEBHOOK_SECRET`` is unset.
    Development may omit the secret for local tests; when set, it is enforced.
    """
    expected = (settings.payphone_webhook_secret or "").strip()
    if not expected:
        if settings.payphone_webhook_secret_required:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="PayPhone webhook is not configured",
            )
        return
    provided = header_secret or query_token
    if not secrets_equal(provided, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid PayPhone webhook secret",
        )


async def _payphone_webhook_response(
    request: Request,
    service: PaymentService,
    *,
    query_token: str | None,
    x_gema_payment_secret: str | None,
) -> JSONResponse:
    _verify_payphone_webhook_secret(
        header_secret=x_gema_payment_secret
        or request.headers.get("x-gema-payment-secret")
        or request.headers.get("x-payphone-webhook-secret"),
        query_token=query_token,
    )
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        service.process_webhook("payphone", headers=headers, body=body)
        payload: dict[str, Any] = {"Response": True, "ErrorCode": "000"}
        return JSONResponse(payload)
    except HTTPException as exc:
        # PayPhone expects its envelope even on business errors.
        code = "111" if exc.status_code >= 500 else "222"
        if exc.status_code == 404:
            code = "444"
        return JSONResponse(
            {"Response": False, "ErrorCode": code},
            status_code=200,
        )
    except Exception:
        return JSONResponse(
            {"Response": False, "ErrorCode": "111"},
            status_code=200,
        )


@router.post("/payments/webhooks/payphone")
@router.post("/payments/webhooks/payphone/NotificacionPago")
async def payphone_webhook(
    request: Request,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    token: Annotated[str | None, Query()] = None,
    x_gema_payment_secret: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    """PayPhone Notificacion Externa — respond with PayPhone's required envelope."""
    return await _payphone_webhook_response(
        request,
        service,
        query_token=token,
        x_gema_payment_secret=x_gema_payment_secret,
    )


@router.post("/payments/webhooks/{provider}", response_model=None)
async def payment_webhook(
    provider: str,
    request: Request,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    x_gema_payment_secret: Annotated[str | None, Header()] = None,
) -> dict | JSONResponse:
    if provider.lower() == "payphone":
        return await _payphone_webhook_response(
            request,
            service,
            query_token=None,
            x_gema_payment_secret=x_gema_payment_secret,
        )

    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    if x_gema_payment_secret:
        headers["x-gema-payment-secret"] = x_gema_payment_secret
    return service.process_webhook(provider, headers=headers, body=body)


@router.get("/admin/payments", response_model=PaymentListResponse)
def admin_list_payments(
    _admin: RequireAdmin,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> PaymentListResponse:
    return service.admin_list(
        page=page,
        page_size=page_size,
        status=status,
        provider=provider,
        q=q,
    )


@router.get("/admin/payments/{payment_id}", response_model=PaymentRead)
def admin_get_payment(
    payment_id: UUID,
    _admin: RequireAdmin,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentRead:
    return service.admin_get(payment_id)
