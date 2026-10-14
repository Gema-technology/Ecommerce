"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
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

export default function AdminPaymentDetailPage() {
  const params = useParams<{ payment_id: string }>();
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await paymentsApi.adminGet(params.payment_id);
        if (!cancelled) setPayment(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "Pago no encontrado",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [params.payment_id]);

  async function confirmPayment(success: boolean) {
    if (!payment) return;
    const ok = await confirm({
      title: success ? "Confirmar pago" : "Marcar pago fallido",
      description: success
        ? "¿Confirmar este depósito/pago? La orden quedará marcada como pagada."
        : "¿Marcar este pago como fallido?",
      confirmLabel: success ? "Confirmar pago" : "Marcar fallido",
      tone: success ? "default" : "danger",
    });
    if (!ok) return;

    setBusy(true);
    setError(null);
    try {
      const updated = await paymentsApi.adminConfirm(payment.id, success);
      setPayment(updated);
      toast.success(
        success
          ? "Pago confirmado. La orden quedó pagada."
          : "Pago marcado como fallido.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo confirmar el pago";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  const canConfirmOffline =
    payment &&
    (payment.provider === "bank_transfer" ||
      payment.provider === "cash_on_delivery" ||
      payment.provider === "manual") &&
    (payment.status === "PROCESSING" || payment.status === "PENDING");

  const marked =
    payment?.client_action?.customer_marked_transferred ||
    Boolean(payment?.metadata?.customer_marked_transferred_at);

  return (
    <AdminShell title="Detalle de pago">
      {confirmDialog}
      <Link href="/admin/payments" className="btn-ghost mb-6 inline-flex">
        ← Pagos
      </Link>
      {error ? (
        <p className="text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}
      {payment ? (
        <>
          <dl className="gema-panel mt-4 space-y-3 p-5 text-sm">
            <div>
              <dt className="text-secondary">ID</dt>
              <dd className="font-mono">{payment.id}</dd>
            </div>
            <div>
              <dt className="text-secondary">Orden</dt>
              <dd>{payment.order_number ?? payment.order_id}</dd>
            </div>
            <div>
              <dt className="text-secondary">Estado</dt>
              <dd>{paymentStatusLabel(payment.status)}</dd>
            </div>
            <div>
              <dt className="text-secondary">Método</dt>
              <dd>{paymentMethodLabel(payment.method)}</dd>
            </div>
            <div>
              <dt className="text-secondary">Monto</dt>
              <dd>{money(payment.amount, payment.currency)}</dd>
            </div>
            <div>
              <dt className="text-secondary">Proveedor</dt>
              <dd>
                {payment.provider}
                {payment.provider_payment_id
                  ? ` · ${payment.provider_payment_id}`
                  : ""}
              </dd>
            </div>
            {payment.provider === "bank_transfer" ? (
              <div>
                <dt className="text-secondary">Cliente marcó transferencia</dt>
                <dd>{marked ? "Sí — verificar en el banco" : "Aún no"}</dd>
              </div>
            ) : null}
          </dl>
          {canConfirmOffline ? (
            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-primary"
                disabled={busy}
                onClick={() => void confirmPayment(true)}
              >
                {busy ? "Confirmando…" : "Confirmar depósito / pago"}
              </button>
              <button
                type="button"
                className="btn-ghost"
                disabled={busy}
                onClick={() => void confirmPayment(false)}
              >
                Marcar fallido
              </button>
            </div>
          ) : null}
        </>
      ) : null}
    </AdminShell>
  );
}
