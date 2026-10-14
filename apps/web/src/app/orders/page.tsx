"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
import { orderStatusLabel, ordersApi, type Order } from "@/lib/orders-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export default function OrdersPage() {
  const { user, loading: authLoading } = useAuth();
  const list = useAdminListParams();
  const [orders, setOrders] = useState<Order[] | null>(null);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await ordersApi.list(list.page, list.pageSize);
      setOrders(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
      setOrders([]);
      setTotal(0);
      setTotalPages(0);
    }
  }, [list.page, list.pageSize]);

  useEffect(() => {
    if (authLoading || !user) return;
    void load();
  }, [user, authLoading, load]);

  const loading = authLoading || (Boolean(user) && orders === null);

  return (
    <StoreShell>
      <main className="gema-container max-w-4xl flex-1 py-10">
        <h1 className="font-display text-2xl font-semibold">Mis órdenes</h1>

        {loading ? (
          <AppLoading
            compact
            label="Cargando pedidos"
            hideHint
            className="!py-16"
          />
        ) : null}

        {!loading && !user ? (
          <div className="mt-8 text-center">
            <p>Inicia sesión para ver tus órdenes.</p>
            <Link href="/login" className="btn-primary mt-4 inline-flex">
              Iniciar sesión
            </Link>
          </div>
        ) : null}

        {error ? (
          <p className="mt-4 text-sm text-error" role="alert">
            {error}
          </p>
        ) : null}

        {!loading && user && orders && orders.length === 0 && !error ? (
          <p className="mt-8 text-sm text-secondary">Aún no tienes órdenes.</p>
        ) : null}

        {!loading && user && orders && orders.length > 0 ? (
          <>
            <ul className="gema-panel mt-8 divide-y divide-border overflow-hidden">
              {orders.map((order) => (
                <li key={order.id}>
                  <Link
                    href={`/orders/${encodeURIComponent(order.order_number)}`}
                    className="flex items-center justify-between gap-3 px-4 py-4 transition hover:bg-surface-elevated"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-medium">{order.order_number}</p>
                      <p className="text-sm text-secondary">
                        {new Date(order.created_at).toLocaleString("es-EC")} ·{" "}
                        {orderStatusLabel(order.status)}
                      </p>
                    </div>
                    <p className="shrink-0 font-semibold">
                      {money(order.total, order.currency)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
            <Pagination
              page={list.page}
              totalPages={totalPages}
              total={total}
              basePath="/orders"
            />
          </>
        ) : null}
      </main>
    </StoreShell>
  );
}
