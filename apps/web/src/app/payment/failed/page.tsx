"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { ApiError } from "@/lib/auth-api";
import {
  paymentsApi,
  paymentStatusLabel,
  type Payment,
} from "@/lib/payments-api";

function PaymentFailedContent() {
  const search = useSearchParams();
  const paymentId = search.get("payment_id");
  const orderNumber = search.get("order_number");
  const { user, loading: authLoading } = useAuth();
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading || !user || !paymentId) return;
    let cancelled = false;
    void (async () => {
      try {
        const data = await paymentsApi.get(paymentId);
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

  const retryHref =
    orderNumber || payment?.order_number
      ? `/orders/${encodeURIComponent(orderNumber || payment!.order_number!)}/payment`
      : "/orders";
  const orderHref =
    orderNumber || payment?.order_number
      ? `/orders/${encodeURIComponent(orderNumber || payment!.order_number!)}`
      : "/orders";

  return (
    <main className="gema-container max-w-lg flex-1 py-10">
      {authLoading ? (
        <AppLoading compact label="Cargando sesión" hideHint className="!py-16" />
      ) : !user ? (
        <div className="text-center">
          <p>Inicia sesión para continuar.</p>
          <Link href="/login" className="btn-primary mt-4 inline-flex">
            Iniciar sesión
          </Link>
        </div>
      ) : (
        <div className="gema-panel p-6">
          <h1 className="font-display text-2xl font-semibold">Pago no completado</h1>
          <p className="mt-2 text-sm text-secondary">
            {payment
              ? `Estado: ${paymentStatusLabel(payment.status)}`
              : "El pago no se confirmó."}
          </p>
          <div className="mt-4 space-y-2 text-sm text-secondary">
            <p>
              La orden sigue pendiente. El stock reservado se liberó al fallar
              el pago; al reintentar se vuelve a reservar automáticamente si hay
              disponibilidad.
            </p>
            <p>
              También puedes cancelar la orden desde el detalle si ya no deseas
              continuar.
            </p>
          </div>
          {error ? (
            <p className="mt-2 text-sm text-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href={retryHref} className="btn-primary">
              Intentar nuevamente
            </Link>
            <Link href={orderHref} className="btn-ghost">
              Ver orden / cancelar
            </Link>
          </div>
        </div>
      )}
    </main>
  );
}

export default function PaymentFailedPage() {
  return (
    <StoreShell>
      <Suspense
        fallback={
          <AppLoading compact label="Cargando pago" hideHint className="!py-16" />
        }
      >
        <PaymentFailedContent />
      </Suspense>
    </StoreShell>
  );
}
