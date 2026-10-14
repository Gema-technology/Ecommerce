"use client";

import { formatPrice } from "@/lib/catalog-types";
import type { Order } from "@/lib/orders-api";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export function OrderTotalsBreakdown({ order }: { order: Order }) {
  const hasDiscount = Number(order.discount_total) > 0;
  const hasShipping = Number(order.shipping_total) > 0;
  const hasTax = Number(order.tax_total) > 0;

  return (
    <div className="space-y-1 text-sm">
      <div className="flex justify-between">
        <span>Subtotal</span>
        <span>{money(order.subtotal, order.currency)}</span>
      </div>
      {hasDiscount ? (
        <div className="flex justify-between text-success">
          <span>Descuento</span>
          <span>−{money(order.discount_total, order.currency)}</span>
        </div>
      ) : null}
      {hasShipping ? (
        <div className="flex justify-between">
          <span>Envío</span>
          <span>{money(order.shipping_total, order.currency)}</span>
        </div>
      ) : null}
      {hasTax ? (
        <div className="flex justify-between">
          <span>IVA</span>
          <span>{money(order.tax_total, order.currency)}</span>
        </div>
      ) : null}
      <div className="flex justify-between border-t border-border pt-2 text-base font-semibold">
        <span>Total</span>
        <span>{money(order.total, order.currency)}</span>
      </div>
    </div>
  );
}
