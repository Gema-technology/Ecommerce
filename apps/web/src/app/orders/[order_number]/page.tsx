"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConfirmCancelDialog } from "@/components/checkout/ConfirmCancelDialog";
import { OrderTotalsBreakdown } from "@/components/checkout/OrderTotalsBreakdown";
import { useAuth } from "@/components/auth/AuthProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { ApiError } from "@/lib/auth-api";
import {
  formatReservationExpiry,
  orderStatusLabel,
  ordersApi,
  type Order,
} from "@/lib/orders-api";
import { formatPrice } from "@/lib/catalog-types";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export default function OrderDetailPage() {
  const params = useParams<{ order_number: string }>();
  const orderNumber = decodeURIComponent(params.order_number);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [showCancelDialog, setShowCancelDialog] = useState(false);

  useEffect(() => {
    if (authLoading || !user) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await ordersApi.getByNumber(orderNumber);
        if (!cancelled) setOrder(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Orden no encontrada",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, orderNumber]);

  async function cancelOrder() {
    if (!order) return;
    setCancelling(true);
    setError(null);
    try {
      const updated = await ordersApi.cancel(order.id);
      setOrder(updated);
      setShowCancelDialog(false);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo cancelar la orden",
      );
    } finally {
      setCancelling(false);
    }
  }

  const reservedLabel = formatReservationExpiry(order?.reserved_until);
  const expiredReservation =
    order?.status === "CANCELLED" &&
    (order.reservations ?? []).some((r) => r.status === "EXPIRED");

  return (
    <StoreShell>
      <main className="gema-container max-w-3xl flex-1 py-10">
        {!authLoading && !user ? (
          <div className="text-center">
            <p>Inicia sesión para ver esta orden.</p>
            <Link href="/login" className="btn-primary mt-4 inline-flex">
              Iniciar sesión
            </Link>
          </div>
        ) : null}

        {(authLoading || (user && !order && !error)) ? (
          <AppLoading compact label="Cargando orden" hideHint className="!py-16" />
        ) : null}

        {error && !order ? (
          <div>
            <h1 className="font-display text-2xl font-semibold">Orden no encontrada</h1>
            <p className="mt-2 text-sm text-secondary">{error}</p>
            <Link href="/orders" className="btn-primary mt-6 inline-flex">
              Mis órdenes
            </Link>
          </div>
        ) : null}

        {order ? (
          <div>
            <p className="text-sm text-secondary">Detalle de compra</p>
            <h1 className="font-display mt-1 text-2xl font-semibold">
              Orden {order.order_number}
            </h1>
            <p className="mt-2 text-sm text-secondary">
              Estado: {orderStatusLabel(order.status)}
            </p>
            <p className="text-sm text-secondary">
              {new Date(order.created_at).toLocaleString("es-EC")}
            </p>

            {error ? (
              <p className="mt-4 text-sm font-medium text-error" role="alert">
                {error}
              </p>
            ) : null}

            {order.status === "PENDING_PAYMENT" && reservedLabel ? (
              <div className="gema-panel mt-6 border-accent/30 bg-surface-image p-4 text-sm">
                <p className="font-medium text-foreground">
                  Reserva de stock activa
                </p>
                <p className="mt-1 text-secondary">
                  Completa el pago antes del{" "}
                  <span className="font-medium text-foreground">
                    {reservedLabel}
                  </span>
                  . Si expira, la orden se cancela y el stock se libera.
                </p>
              </div>
            ) : null}

            {expiredReservation ? (
              <div className="gema-panel mt-6 border-warning/40 p-4 text-sm" role="status">
                <p className="font-medium text-foreground">
                  Reserva expirada
                </p>
                <p className="mt-1 text-secondary">
                  El tiempo de pago venció. Esta orden fue cancelada
                  automáticamente y el inventario quedó disponible.
                </p>
              </div>
            ) : null}

            {order.shipping_address ? (
              <section className="gema-panel mt-8 p-5 text-sm">
                <h2 className="font-display text-base font-semibold">
                  Entrega
                </h2>
                <p className="mt-2 font-medium">
                  {order.shipping_address.recipient_name}
                </p>
                <p className="text-secondary">{order.shipping_address.phone}</p>
                <p className="mt-2 text-secondary">
                  {order.shipping_address.address_line}
                  {order.shipping_address.reference
                    ? ` · ${order.shipping_address.reference}`
                    : ""}
                </p>
                <p className="text-secondary">
                  {order.shipping_address.city},{" "}
                  {order.shipping_address.province},{" "}
                  {order.shipping_address.country}
                  {order.shipping_address.postal_code
                    ? ` · ${order.shipping_address.postal_code}`
                    : ""}
                </p>
                {order.customer_notes ? (
                  <p className="mt-3 text-secondary">
                    <span className="font-medium text-foreground">Notas:</span>{" "}
                    {order.customer_notes}
                  </p>
                ) : null}
              </section>
            ) : null}

            <ul className="gema-panel mt-8 divide-y divide-border overflow-hidden">
              {order.items.map((item) => (
                <li
                  key={item.id}
                  className="flex justify-between gap-4 px-4 py-3 text-sm"
                >
                  <div className="min-w-0">
                    <p className="truncate font-medium">
                      {item.product_name_snapshot}
                    </p>
                    <p className="text-secondary">
                      SKU {item.sku_snapshot} · Cant. {item.quantity}
                    </p>
                  </div>
                  <p className="shrink-0 font-medium">
                    {money(item.line_total, order.currency)}
                  </p>
                </li>
              ))}
            </ul>

            <div className="mt-6">
              <OrderTotalsBreakdown order={order} />
            </div>

            {order.status === "PENDING_PAYMENT" ? (
              <div className="mt-6 flex flex-wrap gap-3">
                <Link
                  href={`/orders/${encodeURIComponent(order.order_number)}/payment`}
                  className="btn-primary"
                >
                  Ir al pago
                </Link>
                <button
                  type="button"
                  className="btn-ghost"
                  disabled={cancelling}
                  onClick={() => setShowCancelDialog(true)}
                >
                  Cancelar orden
                </button>
              </div>
            ) : null}

            <ConfirmCancelDialog
              open={showCancelDialog}
              busy={cancelling}
              onClose={() => setShowCancelDialog(false)}
              onConfirm={() => void cancelOrder()}
            />

            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/orders" className="btn-ghost">
                Mis órdenes
              </Link>
              <button
                type="button"
                className="btn-primary"
                onClick={() => router.push("/products")}
              >
                Seguir comprando
              </button>
            </div>
          </div>
        ) : null}
      </main>
    </StoreShell>
  );
}
