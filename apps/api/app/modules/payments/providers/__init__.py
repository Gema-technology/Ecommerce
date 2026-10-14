from fastapi import HTTPException, status

from app.core.config import settings
from app.modules.payments.providers.bank_transfer import BankTransferPaymentProvider
from app.modules.payments.providers.base import PaymentProvider
from app.modules.payments.providers.cash_on_delivery import CashOnDeliveryPaymentProvider
from app.modules.payments.providers.manual import ManualPaymentProvider
from app.modules.payments.providers.payphone import PayPhonePaymentProvider


def get_provider(name: str | None = None) -> PaymentProvider:
    provider_name = (name or settings.payment_default_provider).lower().strip()
    if provider_name == "manual":
        return ManualPaymentProvider()
    if provider_name == "payphone":
        return PayPhonePaymentProvider()
    if provider_name == "bank_transfer":
        return BankTransferPaymentProvider()
    if provider_name == "cash_on_delivery":
        return CashOnDeliveryPaymentProvider()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=(
            "Invalid PAYMENT_DEFAULT_PROVIDER. Use 'manual' or 'payphone'. "
            "Do not put the PayPhone token in PAYMENT_DEFAULT_PROVIDER; "
            "put it in PAYPHONE_TOKEN."
        ),
    )


def provider_for_method(method: str) -> PaymentProvider:
    """Route offline methods to dedicated providers; cards use the default PSP."""
    upper = method.upper()
    if upper == "BANK_TRANSFER":
        return BankTransferPaymentProvider()
    if upper == "CASH_ON_DELIVERY":
        return CashOnDeliveryPaymentProvider()
    return get_provider()
