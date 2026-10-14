"""Smoke-test PayPhone credentials from the current Settings / .env.

Usage (from apps/api, venv active):

    python -m app.scripts.check_payphone

Creates a $1.00 one-time payment link against PayPhone. Does not mark any
GEMA order as paid. Never prints the full token.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from uuid import uuid4

from app.core.config import settings
from app.modules.payments.providers.base import OrderAmountBreakdown
from app.modules.payments.providers.payphone import PayPhonePaymentProvider


def main() -> int:
    token = (settings.payphone_token or "").strip()
    store = (settings.payphone_store_id or "").strip()
    provider = (settings.payment_default_provider or "").lower()

    print("PayPhone credential check")
    print(f"  APP_ENV={settings.app_env}")
    print(f"  PAYMENT_DEFAULT_PROVIDER={provider}")
    print(f"  PAYPHONE_API_BASE={settings.payphone_api_base}")
    print(f"  PAYPHONE_STORE_ID={'set' if store else 'MISSING'}")
    print(
        f"  PAYPHONE_TOKEN={'set (len=' + str(len(token)) + ')' if token else 'MISSING'}"
    )

    if not token or not store:
        print(
            "\nMissing credentials. In the monorepo root .env set:\n"
            "  PAYMENT_DEFAULT_PROVIDER=payphone\n"
            "  PAYPHONE_TOKEN=<from Payphone Developers → Credenciales>\n"
            "  PAYPHONE_STORE_ID=<from Payphone Developers → Credenciales>\n"
            "Then restart the API and run this script again.\n"
            "Docs: https://docs.payphone.app/configuracion-de-ambiente-y-credenciales"
        )
        return 1

    payment_id = uuid4()
    pp = PayPhonePaymentProvider()
    try:
        result = pp.create_payment(
            payment_id=payment_id,
            order_id=uuid4(),
            order_number="GEMA-PAYPHONE-CHECK",
            amount="1.00",
            currency="USD",
            method="CARD",
            breakdown=OrderAmountBreakdown(
                total=Decimal("1.00"),
                subtotal=Decimal("1.00"),
                tax_total=Decimal("0"),
                shipping_total=Decimal("0"),
                discount_total=Decimal("0"),
            ),
        )
    except Exception as exc:  # noqa: BLE001 — CLI diagnostic
        print(f"\nPayPhone API call FAILED: {exc}")
        print(
            "Check: app type is API (not WEB), environment is PRUEBAS, "
            "token/storeId belong to that app."
        )
        return 2

    url = (result.client_action or {}).get("url")
    print("\nOK — PayPhone accepted the request.")
    print(f"  clientTransactionId={result.provider_payment_id}")
    print(f"  paymentUrl={url}")
    print(
        "\nOpen the URL in a browser, complete a sandbox payment, "
        "then use GEMA checkout with PAYMENT_DEFAULT_PROVIDER=payphone."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
