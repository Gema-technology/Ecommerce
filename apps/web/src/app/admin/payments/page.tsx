"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { FormField, Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
import {
  paymentMethodLabel,
  paymentsApi,
  paymentStatusLabel,
  type Payment,
} from "@/lib/payments-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export default function AdminPaymentsPage() {
  const list = useAdminListParams();
  const status = list.get("status");
  const provider = list.get("provider");

  const [items, setItems] = useState<Payment[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [draftQ, setDraftQ] = useState(list.q);
  const [draftStatus, setDraftStatus] = useState(status);
  const [draftProvider, setDraftProvider] = useState(provider);

  useEffect(() => {
    setDraftQ(list.q);
    setDraftStatus(status);
    setDraftProvider(provider);
  }, [list.q, status, provider]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await paymentsApi.adminList({
        page: list.page,
        page_size: list.pageSize,
        q: list.q || undefined,
        status: status || undefined,
        provider: provider || undefined,
      });
      setItems(data.items);
      setTotal(data.total ?? 0);
      setTotalPages(data.total_pages ?? 0);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudieron cargar pagos",
      );
      setItems([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, status, provider]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      q: draftQ,
      status: draftStatus,
      provider: draftProvider,
    });
  }

  return (
    <AdminShell title="Pagos">
      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftStatus("");
          setDraftProvider("");
          list.clearFilters(["q", "status", "provider"]);
        }}
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Orden o referencia"
          />
        </FormField>
        <FormField label="Estado" className="w-40 min-w-0">
          <Select
            value={draftStatus}
            onChange={(e) => setDraftStatus(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="PENDING">Pendiente</option>
            <option value="PROCESSING">Procesando</option>
            <option value="SUCCEEDED">Exitoso</option>
            <option value="FAILED">Fallido</option>
            <option value="CANCELLED">Cancelado</option>
            <option value="REFUNDED">Reembolsado</option>
          </Select>
        </FormField>
        <FormField label="Proveedor" className="w-44 min-w-0">
          <Select
            value={draftProvider}
            onChange={(e) => setDraftProvider(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="payphone">PayPhone</option>
            <option value="bank_transfer">Transferencia</option>
            <option value="cash_on_delivery">Contra entrega</option>
            <option value="manual">Manual</option>
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={5}
        loading={loading}
        error={error}
        isEmpty={!items.length}
        emptyMessage="Sin pagos aún."
        meta={`${total} pago${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>Orden</th>
            <th>Estado</th>
            <th>Método</th>
            <th>Monto</th>
            <th>Proveedor</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/payments"
          />
        }
      >
        {items.map((p) => (
          <tr key={p.id}>
            <td>
              <Link
                href={`/admin/payments/${p.id}`}
                className="text-cyan underline underline-offset-2"
              >
                {p.order_number ?? p.order_id}
              </Link>
            </td>
            <td>{paymentStatusLabel(p.status)}</td>
            <td>{paymentMethodLabel(p.method)}</td>
            <td>{money(p.amount, p.currency)}</td>
            <td>{p.provider}</td>
          </tr>
        ))}
      </AdminTable>
    </AdminShell>
  );
}
