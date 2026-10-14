"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { OrderTotalsBreakdown } from "@/components/checkout/OrderTotalsBreakdown";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
import {
  formatReservationExpiry,
  orderStatusLabel,
  ordersApi,
  type Order,
} from "@/lib/orders-api";
import {
  paymentMethodLabel,
  paymentsApi,
  paymentStatusLabel,
  type Payment,
} from "@/lib/payments-api";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export default function OrderPaymentPage() {
  const params = useParams<{ order_number: string }>();
  const orderNumber = decodeURIComponent(params.order_number);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [method, setMethod] = useState("CARD");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activePayment, setActivePayment] = useState<Payment | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.allow_cash_on_delivery && method === "CASH_ON_DELIVERY") {
      setMethod("CARD");
    }
  }, [user, method]);

  useEffect(() => {
    if (authLoading || !user) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await ordersApi.getByNumber(orderNumber);
        if (cancelled) return;
        setOrder(data);
        const history = await paymentsApi.listForOrder(data.id);
        if (!cancelled) {
          setPayments(history.items);
          const pendingBank = history.items.find(
            (p) =>
              p.provider === "bank_transfer" &&
              (p.status === "PROCESSING" || p.status === "PENDING"),
          );
          if (pendingBank) setActivePayment(pendingBank);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "No se pudo cargar el pago",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, orderNumber]);

  async function startPayment() {
    if (!order) return;
    setBusy(true);
    setError(null);
    setInfo(null);
    try {
      const payment = await paymentsApi.create(order.id, method);
      const history = await paymentsApi.listForOrder(order.id);
      setPayments(history.items);

      if (payment.provider === "manual") {
        setActivePayment(payment);
        setInfo(
          "Pago registrado. En desarrollo queda pendiente de confirmación del operador.",
        );
        return;
      }

      if (payment.client_action?.type === "bank_transfer_instructions") {
        setActivePayment(payment);
        setInfo(
          "Transfiere el monto exacto a la cuenta indicada. Luego pulsa «Ya transferí».",
        );
        return;
      }

      if (payment.client_action?.type === "cash_on_delivery_pending") {
        setActivePayment(payment);
        setInfo(
          "Pedido registrado con pago contra entrega. Pagarás al recibir; GEMA confirmará el cobro.",
        );
        return;
      }

      const redirectUrl = payment.client_action?.url;
      if (payment.client_action?.type === "redirect" && redirectUrl) {
        setActivePayment(payment);
        setInfo(
          "Se abrirá PayPhone para completar el pago. Cuando termines, vuelve y pulsa «Ya pagué».",
        );
        window.open(redirectUrl, "_blank", "noopener,noreferrer");
        return;
      }

      router.push(
        `/payment/success?payment_id=${encodeURIComponent(payment.id)}`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo iniciar el pago",
      );
    } finally {
      setBusy(false);
    }
  }

  async function verifyPayphonePayment() {
    if (!activePayment) return;
    setBusy(true);
    setError(null);
    try {
      const payment = await paymentsApi.sync(activePayment.id);
      setActivePayment(payment);
      const history = await paymentsApi.listForOrder(payment.order_id);
      setPayments(history.items);
      if (payment.status === "SUCCEEDED") {
        router.push(
          `/payment/success?payment_id=${encodeURIComponent(payment.id)}`,
        );
        return;
      }
      if (payment.status === "FAILED") {
        router.push(
          `/payment/failed?payment_id=${encodeURIComponent(payment.id)}&order_number=${encodeURIComponent(orderNumber)}`,
        );
        return;
      }
      setInfo(
        "PayPhone aún no confirma el pago. Si ya pagaste, espera unos segundos y vuelve a verificar.",
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo verificar el pago con PayPhone",
      );
    } finally {
      setBusy(false);
    }
  }

  async function markTransferred() {
    if (!activePayment) return;
    setBusy(true);
    setError(null);
    try {
      const payment = await paymentsApi.markTransferred(activePayment.id);
      setActivePayment(payment);
      const history = await paymentsApi.listForOrder(payment.order_id);
      setPayments(history.items);
      setInfo(
        "Registramos que ya transferiste. Un operador verificará el depósito y confirmará tu orden.",
      );
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo registrar la transferencia",
      );
    } finally {
      setBusy(false);
    }
  }

  const bankAction =
    activePayment?.client_action?.type === "bank_transfer_instructions"
      ? activePayment.client_action
      : null;

  const canPay = order?.status === "PENDING_PAYMENT";
  const reservedLabel = formatReservationExpiry(order?.reserved_until);
  const expiredReservation =
    order?.status === "CANCELLED" &&
    (order.reservations ?? []).some((r) => r.status === "EXPIRED");

  return (
    <StoreShell>
      <main className="gema-container max-w-3xl flex-1 py-10">
        {!authLoading && !user ? (
          <div className="text-center">
            <p>Inicia sesión para pagar esta orden.</p>
            <Link href="/login" className="btn-primary mt-4 inline-flex">
              Iniciar sesión
            </Link>
          </div>
        ) : null}

        {authLoading || (loading && user) ? (
          <AppLoading
            compact
            label={authLoading ? "Cargando sesión" : "Cargando pago"}
            hideHint
            className="!py-16"
          />
        ) : null}

        {error && !order ? (
          <div>
            <h1 className="font-display text-2xl font-semibold">Pago</h1>
            <p className="mt-2 text-sm text-secondary">{error}</p>
            <Link href="/orders" className="btn-primary mt-6 inline-flex">
              Mis órdenes
            </Link>
          </div>
        ) : null}

        {order ? (
          <div>
            <h1 className="font-display text-2xl font-semibold">Pago de orden</h1>
            <p className="mt-2 text-sm text-secondary">
              Orden {order.order_number}
            </p>
            <p className="text-sm text-secondary">
              Estado: {orderStatusLabel(order.status)}
            </p>

            {canPay && reservedLabel ? (
              <div className="gema-panel mt-6 border-accent/30 bg-surface-image p-4 text-sm">
                <p className="font-medium text-foreground">
                  Completa el pago antes del {reservedLabel}
                </p>
                <p className="mt-1 text-secondary">
                  Si la reserva expira, la orden se cancela y el stock se libera.
                </p>
              </div>
            ) : null}

            {order.status === "CANCELLED" ? (
              <div className="gema-panel mt-6 border-warning/40 p-4 text-sm" role="status">
                <p className="font-medium text-foreground">
                  {expiredReservation
                    ? "Orden cancelada por reserva expirada"
                    : "Orden cancelada"}
                </p>
                <p className="mt-1 text-secondary">
                  {expiredReservation
                    ? "El tiempo de pago venció. Vuelve al catálogo y crea una nueva compra si aún deseas los productos."
                    : "Esta orden ya no admite pago. Si aún quieres comprar, crea una nueva orden desde el carrito."}
                </p>
              </div>
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

            {canPay ? (
              <div className="gema-panel mt-8 space-y-4 p-5">
                <label className="block text-sm">
                  <span className="label-field">Método de pago</span>
                  <Select
                    className="mt-1.5"
                    value={method}
                    onChange={(e) => setMethod(e.target.value)}
                    disabled={busy}
                  >
                    <option value="CARD">Tarjeta</option>
                    <option value="BANK_TRANSFER">Transferencia bancaria</option>
                    {user?.allow_cash_on_delivery ? (
                      <option value="CASH_ON_DELIVERY">Contra entrega</option>
                    ) : null}
                  </Select>
                </label>
                <p className="text-xs text-secondary">
                  El monto se toma de la orden en el servidor ({order.currency}).
                  Tarjeta abre PayPhone. Transferencia muestra la cuenta bancaria
                  de GEMA. Contra entrega solo aparece si GEMA te habilitó como
                  cliente de confianza.
                </p>
                {bankAction?.bank ? (
                  <div className="rounded-lg border border-border bg-surface-image p-4 text-sm">
                    <p className="font-medium text-foreground">
                      Datos para transferencia
                    </p>
                    <dl className="mt-3 space-y-1.5 text-secondary">
                      <div className="flex justify-between gap-3">
                        <dt>Banco</dt>
                        <dd className="text-right text-foreground">
                          {bankAction.bank.bank_name}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Tipo de cuenta</dt>
                        <dd className="text-right text-foreground">
                          {bankAction.bank.account_type}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Número</dt>
                        <dd className="text-right font-mono text-foreground">
                          {bankAction.bank.account_number}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Titular</dt>
                        <dd className="text-right text-foreground">
                          {bankAction.bank.account_holder}
                        </dd>
                      </div>
                      {bankAction.bank.account_id ? (
                        <div className="flex justify-between gap-3">
                          <dt>CI / RUC</dt>
                          <dd className="text-right font-mono text-foreground">
                            {bankAction.bank.account_id}
                          </dd>
                        </div>
                      ) : null}
                      <div className="flex justify-between gap-3">
                        <dt>Monto</dt>
                        <dd className="text-right font-semibold text-foreground">
                          {money(
                            bankAction.amount ?? order.total,
                            bankAction.currency ?? order.currency,
                          )}
                        </dd>
                      </div>
                      <div className="flex justify-between gap-3">
                        <dt>Referencia</dt>
                        <dd className="text-right font-mono text-foreground">
                          {bankAction.reference}
                        </dd>
                      </div>
                    </dl>
                    {bankAction.bank.extra_instructions ? (
                      <p className="mt-3 text-xs text-secondary">
                        {bankAction.bank.extra_instructions}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {info ? (
                  <p className="text-sm text-secondary" role="status">
                    {info}
                  </p>
                ) : null}
                {error ? (
                  <p className="text-sm text-error" role="alert">
                    {error}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-3">
                  <button
                    type="button"
                    className="btn-primary"
                    disabled={busy}
                    onClick={() => void startPayment()}
                  >
                    {busy
                      ? "Procesando…"
                      : method === "BANK_TRANSFER"
                        ? "Ver datos bancarios"
                        : activePayment?.provider === "payphone"
                          ? "Generar otro link PayPhone"
                          : "Iniciar pago"}
                  </button>
                  {activePayment?.provider === "payphone" &&
                  activePayment.status !== "SUCCEEDED" ? (
                    <button
                      type="button"
                      className="btn-ghost"
                      disabled={busy}
                      onClick={() => void verifyPayphonePayment()}
                    >
                      Ya pagué — verificar
                    </button>
                  ) : null}
                  {activePayment?.provider === "bank_transfer" &&
                  activePayment.status !== "SUCCEEDED" ? (
                    <button
                      type="button"
                      className="btn-ghost"
                      disabled={
                        busy ||
                        Boolean(
                          activePayment.client_action
                            ?.customer_marked_transferred,
                        )
                      }
                      onClick={() => void markTransferred()}
                    >
                      {activePayment.client_action
                        ?.customer_marked_transferred
                        ? "Transferencia registrada"
                        : "Ya transferí"}
                    </button>
                  ) : null}
                  {activePayment?.client_action?.url ? (
                    <a
                      href={activePayment.client_action.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="btn-ghost"
                    >
                      Reabrir PayPhone
                    </a>
                  ) : null}
                </div>
              </div>
            ) : order.status !== "CANCELLED" ? (
              <p className="mt-8 text-sm text-secondary">
                Esta orden no admite un nuevo pago (
                {orderStatusLabel(order.status)}).
              </p>
            ) : null}

            {payments.length ? (
              <div className="mt-10">
                <h2 className="font-display text-lg font-semibold">Intentos de pago</h2>
                <ul className="mt-3 space-y-2 text-sm">
                  {payments.map((p) => (
                    <li
                      key={p.id}
                      className="flex justify-between gap-3"
                    >
                      <span className="min-w-0 break-words">
                        {paymentMethodLabel(p.method)} ·{" "}
                        {paymentStatusLabel(p.status)}
                      </span>
                      <span className="shrink-0">
                        {money(p.amount, p.currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href={`/orders/${encodeURIComponent(order.order_number)}`}
                className="btn-ghost"
              >
                Volver a la orden
              </Link>
              {order.status === "CANCELLED" ? (
                <Link href="/products" className="btn-primary">
                  Ir al catálogo
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
      </main>
    </StoreShell>
  );
}
