import type { Cart } from "@/lib/cart-api";
import { formatPrice } from "@/lib/catalog-types";
import { shippingMethodLabel } from "@/lib/checkout-types";
import type { CheckoutPreview } from "@/lib/orders-api";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

type Props = {
  cart: Cart | null;
  preview: CheckoutPreview | null;
  loadingPreview?: boolean;
};

export function CheckoutSummary({ cart, preview, loadingPreview }: Props) {
  const currency = preview?.currency ?? cart?.currency ?? "USD";
  const subtotal = preview?.subtotal ?? cart?.subtotal ?? "0";
  const discount = preview?.discount_total ?? "0";
  const shipping = preview?.shipping_total ?? "0";
  const tax = preview?.tax_total ?? "0";
  const total = preview?.total ?? cart?.subtotal ?? "0";

  return (
    <aside className="gema-panel-elevated h-fit p-6 lg:sticky lg:top-28">
      <h2 className="font-display text-lg font-semibold text-navy">Resumen</h2>
      <ul className="mt-4 divide-y divide-border">
        {preview
          ? preview.items.map((item) => (
              <li
                key={item.product_id}
                className="flex justify-between gap-3 py-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">
                    {item.product_name}
                  </p>
                  <p className="text-secondary">× {item.quantity}</p>
                </div>
                <p className="shrink-0 font-medium">
                  {money(item.line_total, currency)}
                </p>
              </li>
            ))
          : (cart?.items ?? []).map((item) => (
              <li
                key={item.id}
                className="flex justify-between gap-3 py-3 text-sm"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium text-foreground">
                    {item.product.name}
                  </p>
                  <p className="text-secondary">
                    × {item.quantity}
                    {!item.available || !item.product.is_active
                      ? " · No disponible"
                      : ""}
                  </p>
                </div>
                <p className="shrink-0 font-medium">
                  {item.line_total ? money(item.line_total, currency) : "—"}
                </p>
              </li>
            ))}
      </ul>

      <dl className="mt-4 space-y-2 border-t border-border pt-4 text-sm">
        <div className="flex justify-between">
          <dt className="text-secondary">Subtotal</dt>
          <dd>{money(subtotal, currency)}</dd>
        </div>
        {Number(discount) > 0 ? (
          <div className="flex justify-between text-success">
            <dt>Descuento</dt>
            <dd>−{money(discount, currency)}</dd>
          </div>
        ) : null}
        <div className="flex justify-between">
          <dt className="text-secondary">
            Envío
            {preview?.shipping_method ? (
              <span className="ml-1 text-xs text-muted">
                ({shippingMethodLabel(preview.shipping_method)})
              </span>
            ) : null}
          </dt>
          <dd>
            {loadingPreview ? (
              <span className="text-muted">Calculando…</span>
            ) : (
              money(shipping, currency)
            )}
          </dd>
        </div>
        {preview?.tax_enabled || Number(tax) > 0 ? (
          <div className="flex justify-between">
            <dt className="text-secondary">IVA</dt>
            <dd>
              {loadingPreview ? (
                <span className="text-muted">—</span>
              ) : (
                money(tax, currency)
              )}
            </dd>
          </div>
        ) : preview ? (
          <div className="flex justify-between">
            <dt className="text-secondary">IVA</dt>
            <dd className="text-muted">{money("0", currency)}</dd>
          </div>
        ) : null}
        <div className="flex justify-between border-t border-border pt-3 text-base font-semibold">
          <dt className="font-display text-navy">Total</dt>
          <dd className="font-display text-navy">
            {loadingPreview ? "…" : money(total, currency)}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs text-muted">
        Los totales se calculan en el servidor. El monto final se confirma al
        crear tu orden.
      </p>
    </aside>
  );
}
