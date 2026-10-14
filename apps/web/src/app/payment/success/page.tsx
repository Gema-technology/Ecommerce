"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
import {
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

function PaymentSuccessContent() {
  const search = useSearchParams();
  const paymentId = search.get("payment_id");
  const { user, loading: authLoading } = useAuth();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !user || !paymentId) return;
    let cancelled = false;
    void (async () => {
      try {
        let data = await paymentsApi.get(paymentId);
        if (
          !cancelled &&
          data.provider === "payphone" &&
          data.status !== "SUCCEEDED" &&
          data.status !== "FAILED"
        ) {
          try {
            data = await paymentsApi.sync(paymentId);
          } catch {
            // Keep last known status if PayPhone has not settled yet.
          }
        }
        if (!cancelled) setPayment(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : "No se pudo verificar el pago",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading, paymentId]);

  const verifying = Boolean(
    !authLoading && user && paymentId && !payment && !error,
  );
  const succeeded = payment?.status === "SUCCEEDED";

  return (
    <main className="gema-container max-w-lg flex-1 py-10">
      {!authLoading && !user ? (
        <div className="text-center">
          <p>Inicia sesión para verificar el pago.</p>
          <Link href="/login" className="btn-primary mt-4 inline-flex">
            Iniciar sesión
          </Link>
        </div>
      ) : null}

      {!paymentId ? (
        <div>
          <h1 className="font-display text-2xl font-semibold">Pago</h1>
          <p className="mt-2 text-sm text-secondary">
            Falta el identificador de pago. El estado se confirma solo desde el
            backend.
          </p>
        </div>
      ) : null}

      {authLoading || verifying ? (
        <AppLoading
          compact
          label={authLoading ? "Cargando sesión" : "Verificando pago"}
          hideHint
          className="!py-16"
        />
      ) : null}

      {error ? (
        <div>
          <h1 className="font-display text-2xl font-semibold">No verificado</h1>
          <p className="mt-2 text-sm text-secondary">{error}</p>
        </div>
      ) : null}

      {payment ? (
        <div className="gema-panel p-6">
          <h1 className="font-display text-2xl font-semibold">
            {succeeded ? "Pago confirmado" : "Pago no confirmado"}
          </h1>
          <p className="mt-2 text-sm text-secondary">
            Estado: {paymentStatusLabel(payment.status)}
          </p>
          {payment.order_number ? (
            <p className="text-sm text-secondary">
              Orden {payment.order_number}
            </p>
          ) : null}
          <p className="mt-4 text-base font-semibold">
            {money(payment.amount, payment.currency)}
          </p>
          {!succeeded ? (
            <p className="mt-4 text-sm text-secondary">
              La redirección no implica éxito. El backend indica{" "}
              {paymentStatusLabel(payment.status)}.
            </p>
          ) : null}
          <div className="mt-8 flex flex-wrap gap-3">
            {payment.order_number ? (
              <Link
                href={`/orders/${encodeURIComponent(payment.order_number)}`}
                className="btn-primary"
              >
                Ver orden
              </Link>
            ) : null}
            {!succeeded && payment.order_number ? (
              <Link
                href={`/orders/${encodeURIComponent(payment.order_number)}/payment`}
                className="btn-ghost"
              >
                Intentar nuevamente
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}
    </main>
  );
}

export default function PaymentSuccessPage() {
  return (
    <StoreShell>
      <Suspense
        fallback={
          <AppLoading compact label="Cargando pago" hideHint className="!py-16" />
        }
      >
        <PaymentSuccessContent />
      </Suspense>
    </StoreShell>
  );
}
