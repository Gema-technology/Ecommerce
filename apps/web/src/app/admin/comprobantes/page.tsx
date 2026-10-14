"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
import {
  fiscalStatusLabel,
  sriApi,
  type FiscalDocument,
} from "@/lib/sri-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export default function AdminComprobantesPage() {
  const router = useRouter();
  const list = useAdminListParams();
  const [items, setItems] = useState<FiscalDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await sriApi.listDocuments(list.page, list.pageSize);
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        router.replace("/login?next=/admin/comprobantes");
        return;
      }
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudieron cargar los comprobantes",
      );
      setItems([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, router]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <AdminShell title="Comprobantes fiscales">
      {error ? (
        <p className="mb-4 text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-secondary">Cargando…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-secondary">
          Aún no hay notas de venta ni facturas. Emítelas desde el detalle de
          un pedido pagado.
        </p>
      ) : (
        <>
          <p className="mb-3 font-mono text-xs text-muted">
            {total} comprobante{total === 1 ? "" : "s"}
          </p>
          <ul className="gema-panel divide-y divide-border overflow-hidden">
            {items.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="text-sm">
                  <p className="font-medium">
                    {doc.doc_type === "FACTURA" ? "Factura" : "Nota de venta"}{" "}
                    {doc.document_number}
                  </p>
                  <p className="text-secondary">
                    {doc.buyer_name} · {fiscalStatusLabel(doc.status)} ·{" "}
                    {money(doc.total, doc.currency)}
                  </p>
                  <p className="text-xs text-muted">
                    {new Date(doc.created_at).toLocaleString("es-EC")}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Link
                    href={`/admin/orders/${doc.order_id}`}
                    className="btn-ghost text-sm"
                  >
                    Pedido
                  </Link>
                  {doc.has_pdf ? (
                    <a
                      href={sriApi.pdfUrl(doc.id)}
                      className="btn-ghost text-sm"
                      target="_blank"
                      rel="noreferrer"
                    >
                      PDF
                    </a>
                  ) : null}
                  {doc.has_xml ? (
                    <a
                      href={sriApi.xmlUrl(doc.id)}
                      className="btn-ghost text-sm"
                      target="_blank"
                      rel="noreferrer"
                    >
                      XML
                    </a>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/comprobantes"
          />
        </>
      )}
    </AdminShell>
  );
}
