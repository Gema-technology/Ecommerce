"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { FormField, Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import {
  formatUsd,
  quoteStatusLabel,
  quotesApi,
  type Quote,
} from "@/lib/quotes-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

export default function AdminCotizacionesPage() {
  const list = useAdminListParams();
  const status = list.get("status");
  const client = list.get("client");
  const dateFrom = list.get("date_from");
  const dateTo = list.get("date_to");

  const [quotes, setQuotes] = useState<Quote[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [draftStatus, setDraftStatus] = useState(status);
  const [draftClient, setDraftClient] = useState(client);
  const [draftFrom, setDraftFrom] = useState(dateFrom);
  const [draftTo, setDraftTo] = useState(dateTo);

  useEffect(() => {
    setDraftStatus(status);
    setDraftClient(client);
    setDraftFrom(dateFrom);
    setDraftTo(dateTo);
  }, [status, client, dateFrom, dateTo]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await quotesApi.listQuotes({
        status: status || undefined,
        client: client || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page: list.page,
        page_size: list.pageSize,
      });
      setQuotes(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
      setQuotes([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, status, client, dateFrom, dateTo]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      status: draftStatus,
      client: draftClient,
      date_from: draftFrom,
      date_to: draftTo,
    });
  }

  return (
    <AdminShell title="Cotizaciones">
      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftStatus("");
          setDraftClient("");
          setDraftFrom("");
          setDraftTo("");
          list.clearFilters(["status", "client", "date_from", "date_to"]);
        }}
        actions={
          <Link href="/admin/cotizaciones/nueva" className="btn-primary">
            Nueva cotización
          </Link>
        }
      >
        <FormField label="Estado" className="w-44 min-w-0">
          <Select
            value={draftStatus}
            onChange={(e) => setDraftStatus(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="draft">Borrador</option>
            <option value="sent">Enviada</option>
            <option value="accepted">Aceptada</option>
            <option value="rejected">Rechazada</option>
            <option value="expired">Expirada</option>
          </Select>
        </FormField>
        <FormField label="Cliente / número" className="w-56 min-w-0">
          <Input
            value={draftClient}
            onChange={(e) => setDraftClient(e.target.value)}
            placeholder="Buscar…"
          />
        </FormField>
        <FormField label="Desde" className="w-40 min-w-0">
          <Input
            type="date"
            value={draftFrom}
            onChange={(e) => setDraftFrom(e.target.value)}
          />
        </FormField>
        <FormField label="Hasta" className="w-40 min-w-0">
          <Input
            type="date"
            value={draftTo}
            onChange={(e) => setDraftTo(e.target.value)}
          />
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={6}
        loading={loading}
        error={error}
        isEmpty={!quotes.length}
        emptyMessage="No hay cotizaciones."
        meta={`${total} cotización${total === 1 ? "" : "es"}`}
        head={
          <tr>
            <th>Número</th>
            <th>Cliente</th>
            <th>Fecha</th>
            <th>Estado</th>
            <th>Total</th>
            <th>Acciones</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/cotizaciones"
          />
        }
      >
        {quotes.map((q) => (
          <tr key={q.id}>
            <td>
              <Link
                href={`/admin/cotizaciones/${q.id}`}
                className="text-cyan underline"
              >
                {q.number}
              </Link>
            </td>
            <td>{q.client_name}</td>
            <td>{new Date(q.created_at).toLocaleString("es-EC")}</td>
            <td>{quoteStatusLabel(q.status)}</td>
            <td>{formatUsd(q.total)}</td>
            <td>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/admin/cotizaciones/${q.id}`}
                  className="btn-ghost btn-sm"
                >
                  Ver
                </Link>
                <a
                  href={quotesApi.pdfUrl(q.id)}
                  className="btn-ghost btn-sm"
                  target="_blank"
                  rel="noreferrer"
                >
                  PDF
                </a>
              </div>
            </td>
          </tr>
        ))}
      </AdminTable>
    </AdminShell>
  );
}
