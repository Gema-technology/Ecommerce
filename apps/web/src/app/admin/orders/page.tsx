"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { FormField, Select } from "@/components/ui/input";
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

const STATUS_OPTIONS = [
  "PENDING_PAYMENT",
  "PAID",
  "PROCESSING",
  "SHIPPED",
  "DELIVERED",
  "CANCELLED",
] as const;

export default function AdminOrdersPage() {
  const list = useAdminListParams();
  const status = list.get("status");
  const [orders, setOrders] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [draftStatus, setDraftStatus] = useState(status);

  useEffect(() => {
    setDraftStatus(status);
  }, [status]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await ordersApi.adminList({
        page: list.page,
        page_size: list.pageSize,
        status: status || undefined,
      });
      setOrders(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
      setOrders([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, status]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({ status: draftStatus });
  }

  return (
    <AdminShell title="Pedidos">
      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftStatus("");
          list.clearFilters(["status"]);
        }}
      >
        <FormField label="Estado" className="w-52 min-w-0">
          <Select
            value={draftStatus}
            onChange={(e) => setDraftStatus(e.target.value)}
          >
            <option value="">Todos</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {orderStatusLabel(s)}
              </option>
            ))}
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={5}
        loading={loading}
        error={error}
        isEmpty={!orders.length}
        emptyMessage="No hay pedidos."
        meta={`${total} pedido${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>Número</th>
            <th>Cliente</th>
            <th>Fecha</th>
            <th>Estado</th>
            <th>Total</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/orders"
          />
        }
      >
        {orders.map((order) => (
          <tr key={order.id}>
            <td>
              <Link
                href={`/admin/orders/${order.id}`}
                className="text-cyan underline"
              >
                {order.order_number}
              </Link>
            </td>
            <td>{order.customer_email ?? "—"}</td>
            <td>{new Date(order.created_at).toLocaleString("es-EC")}</td>
            <td>{orderStatusLabel(order.status)}</td>
            <td>{money(order.total, order.currency)}</td>
          </tr>
        ))}
      </AdminTable>
    </AdminShell>
  );
}
