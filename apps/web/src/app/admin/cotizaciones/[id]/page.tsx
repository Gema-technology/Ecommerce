"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { FormField, Select } from "@/components/ui/input";
import { ApiError } from "@/lib/auth-api";
import {
  formatUsd,
  quoteStatusLabel,
  quotesApi,
  tierLabel,
  type Quote,
} from "@/lib/quotes-api";

export default function CotizacionDetallePage() {
  const params = useParams<{ id: string }>();
  const [quote, setQuote] = useState<Quote | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const data = await quotesApi.getQuote(params.id);
    setQuote(data);
    setStatus(data.status);
  }, [params.id]);

  useEffect(() => {
    void load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    });
  }, [load]);

  async function updateStatus() {
    if (!quote) return;
    setSaving(true);
    setError(null);
    try {
      const updated = await quotesApi.updateQuote(quote.id, { status });
      setQuote(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar");
    } finally {
      setSaving(false);
    }
  }

  if (!quote && !error) {
    return (
      <AdminShell title="Cotización">
        <p className="text-secondary">Cargando…</p>
      </AdminShell>
    );
  }

  return (
    <AdminShell title={quote ? quote.number : "Cotización"}>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link href="/admin/cotizaciones" className="btn-ghost btn-sm">
          ← Historial
        </Link>
        {quote ? (
          <>
            <a
              href={quotesApi.pdfUrl(quote.id)}
              className="btn-primary"
              target="_blank"
              rel="noreferrer"
            >
              Descargar PDF
            </a>
            {quote.client_email ? (
              <a
                href={`mailto:${quote.client_email}?subject=${encodeURIComponent(`Proforma ${quote.number}`)}&body=${encodeURIComponent("Adjunto encontrará nuestra proforma. Descargue el PDF desde el panel admin.")}`}
                className="btn-secondary"
              >
                Enviar por email
              </a>
            ) : null}
          </>
        ) : null}
      </div>

      {error ? (
        <p className="mb-4 text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      {quote ? (
        <div className="grid gap-8 lg:grid-cols-2">
          <section className="gema-panel p-5">
            <h2 className="font-display mb-4 text-lg font-semibold">Cliente</h2>
            <dl className="space-y-2 text-sm">
              <div>
                <dt className="text-secondary">Nombre</dt>
                <dd>{quote.client_name}</dd>
              </div>
              {quote.client_id_number ? (
                <div>
                  <dt className="text-secondary">Identificación</dt>
                  <dd>{quote.client_id_number}</dd>
                </div>
              ) : null}
              {quote.client_phone ? (
                <div>
                  <dt className="text-secondary">Teléfono</dt>
                  <dd>{quote.client_phone}</dd>
                </div>
              ) : null}
              {quote.client_email ? (
                <div>
                  <dt className="text-secondary">Correo</dt>
                  <dd>{quote.client_email}</dd>
                </div>
              ) : null}
              {quote.client_address ? (
                <div>
                  <dt className="text-secondary">Dirección</dt>
                  <dd>{quote.client_address}</dd>
                </div>
              ) : null}
              {quote.valid_until ? (
                <div>
                  <dt className="text-secondary">Válida hasta</dt>
                  <dd>{new Date(quote.valid_until).toLocaleDateString("es-EC")}</dd>
                </div>
              ) : null}
            </dl>

            <div className="mt-6 flex flex-wrap items-end gap-3">
              <FormField label="Estado" className="w-44 min-w-0">
                <Select value={status} onChange={(e) => setStatus(e.target.value)}>
                  <option value="draft">Borrador</option>
                  <option value="sent">Enviada</option>
                  <option value="accepted">Aceptada</option>
                  <option value="rejected">Rechazada</option>
                  <option value="expired">Expirada</option>
                </Select>
              </FormField>
              <button
                type="button"
                className="btn-secondary"
                disabled={saving || status === quote.status}
                onClick={() => void updateStatus()}
              >
                {saving ? "Guardando…" : "Actualizar estado"}
              </button>
            </div>
            <p className="mt-2 text-xs text-secondary">
              Estado actual: {quoteStatusLabel(quote.status)}
            </p>
          </section>

          <section className="gema-panel p-5">
            <h2 className="font-display mb-4 text-lg font-semibold">Detalle</h2>
            <div className="mb-4 overflow-x-auto">
              <table className="gema-table text-sm">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>Tier</th>
                    <th>Cant.</th>
                    <th>P. unit.</th>
                    <th>Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {quote.items.map((item) => (
                    <tr key={item.id}>
                      <td>{item.product_name}</td>
                      <td>{item.tier ? tierLabel(item.tier) : "—"}</td>
                      <td>{item.quantity}</td>
                      <td>{formatUsd(item.unit_price)}</td>
                      <td>{formatUsd(item.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="space-y-1 border-t border-border pt-4 text-sm">
              <div className="flex justify-between">
                <span>Subtotal</span>
                <span>{formatUsd(quote.subtotal)}</span>
              </div>
              <div className="flex justify-between">
                <span>IVA</span>
                <span>{formatUsd(quote.iva_amount)}</span>
              </div>
              <div className="flex justify-between text-base font-semibold">
                <span>Total USD</span>
                <span>{formatUsd(quote.total)}</span>
              </div>
            </div>

            {quote.notes ? (
              <div className="mt-6 rounded border border-border bg-surface-hover p-3 text-sm">
                <strong>Notas</strong>
                <p className="mt-1 whitespace-pre-wrap">{quote.notes}</p>
              </div>
            ) : null}

            <p className="mt-4 text-xs text-secondary">
              Creada el {new Date(quote.created_at).toLocaleString("es-EC")}
              {quote.created_by_email ? ` por ${quote.created_by_email}` : ""}
            </p>
          </section>
        </div>
      ) : null}
    </AdminShell>
  );
}
