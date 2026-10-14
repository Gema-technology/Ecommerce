"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { FieldRow, FormSection } from "@/components/admin/forms/AdminFormPrimitives";
import { FormField, Input, Select, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/auth-api";
import {
  formatUsd,
  marginToPercent,
  previewQuoteTotals,
  quotesApi,
  tierLabel,
  type QuoteProduct,
} from "@/lib/quotes-api";

type LineDraft = {
  key: string;
  product_id: string;
  tier: "min" | "rec" | "high" | "manual";
  quantity: number;
  manual_price: string;
};

function unitPriceFor(product: QuoteProduct, tier: LineDraft["tier"], manual: string): number {
  if (tier === "min") return parseFloat(product.price_min);
  if (tier === "high") return parseFloat(product.price_high);
  if (tier === "manual") return parseFloat(manual) || 0;
  return parseFloat(product.price_rec);
}

export default function NuevaCotizacionPage() {
  const router = useRouter();
  const [products, setProducts] = useState<QuoteProduct[]>([]);
  const [ivaPct, setIvaPct] = useState(15);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [client, setClient] = useState({
    client_name: "",
    client_id_number: "",
    client_phone: "",
    client_email: "",
    client_address: "",
    valid_until: "",
    notes: "",
  });
  const [lines, setLines] = useState<LineDraft[]>([]);
  const [addProductId, setAddProductId] = useState("");

  useEffect(() => {
    void (async () => {
      try {
        const [catalog, config] = await Promise.all([
          quotesApi.listProducts({ active_only: true, page_size: 100 }),
          quotesApi.getPricingConfig(),
        ]);
        setProducts(catalog.items);
        setIvaPct(marginToPercent(config.default_iva));
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Error al cargar catálogo");
      }
    })();
  }, []);

  const previewLines = useMemo(() => {
    return lines
      .map((line) => {
        const product = products.find((p) => p.id === line.product_id);
        if (!product) return null;
        const unitPrice = unitPriceFor(product, line.tier, line.manual_price);
        return {
          name: product.name,
          tier: line.tier,
          quantity: line.quantity,
          unitPrice,
          lineTotal: unitPrice * line.quantity,
        };
      })
      .filter(Boolean) as {
      name: string;
      tier: string;
      quantity: number;
      unitPrice: number;
      lineTotal: number;
    }[];
  }, [lines, products]);

  const totals = previewQuoteTotals(
    previewLines.map((l) => ({ quantity: l.quantity, unitPrice: l.unitPrice })),
    ivaPct / 100,
  );

  function addLine() {
    if (!addProductId) return;
    setLines((prev) => [
      ...prev,
      {
        key: `${addProductId}-${Date.now()}`,
        product_id: addProductId,
        tier: "rec",
        quantity: 1,
        manual_price: "",
      },
    ]);
    setAddProductId("");
  }

  async function save() {
    if (!client.client_name.trim() || !lines.length) {
      setError("Completa el cliente y al menos un ítem.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await quotesApi.createQuote({
        client_name: client.client_name,
        client_id_number: client.client_id_number || null,
        client_phone: client.client_phone || null,
        client_email: client.client_email || null,
        client_address: client.client_address || null,
        valid_until: client.valid_until || null,
        notes: client.notes || null,
        iva_pct: (ivaPct / 100).toFixed(4),
        status: "draft",
        items: lines.map((line) => ({
          product_id: line.product_id,
          tier: line.tier,
          quantity: line.quantity,
          unit_price:
            line.tier === "manual" && line.manual_price ? line.manual_price : undefined,
        })),
      });
      router.push(`/admin/cotizaciones/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear la cotización");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell title="Nueva cotización">
      <div className="mb-4">
        <Link href="/admin/cotizaciones" className="btn-ghost text-sm">
          ← Volver al historial
        </Link>
      </div>

      {error ? (
        <p className="mb-4 text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-6">
          <section className="gema-panel p-6">
            <div className="admin-form">
              <FormSection label="Cliente">
                <FormField label="Nombre del cliente" required>
                  <Input
                    required
                    value={client.client_name}
                    onChange={(e) => setClient((c) => ({ ...c, client_name: e.target.value }))}
                    placeholder="Nombre o razón social"
                  />
                </FormField>
                <FieldRow>
                  <FormField label="Identificación">
                    <Input
                      className="mono-input"
                      value={client.client_id_number}
                      onChange={(e) =>
                        setClient((c) => ({ ...c, client_id_number: e.target.value }))
                      }
                    />
                  </FormField>
                  <FormField label="Teléfono">
                    <Input
                      value={client.client_phone}
                      onChange={(e) => setClient((c) => ({ ...c, client_phone: e.target.value }))}
                    />
                  </FormField>
                </FieldRow>
                <FieldRow>
                  <FormField label="Correo">
                    <Input
                      type="email"
                      value={client.client_email}
                      onChange={(e) => setClient((c) => ({ ...c, client_email: e.target.value }))}
                    />
                  </FormField>
                  <FormField label="Válida hasta">
                    <Input
                      type="date"
                      className="mono-input"
                      value={client.valid_until}
                      onChange={(e) => setClient((c) => ({ ...c, valid_until: e.target.value }))}
                    />
                  </FormField>
                </FieldRow>
                <FormField label="Dirección">
                  <Input
                    value={client.client_address}
                    onChange={(e) => setClient((c) => ({ ...c, client_address: e.target.value }))}
                  />
                </FormField>
                <FormField label="Notas y condiciones">
                  <Textarea
                    rows={3}
                    value={client.notes}
                    onChange={(e) => setClient((c) => ({ ...c, notes: e.target.value }))}
                    placeholder="Condiciones de pago, entrega…"
                  />
                </FormField>
              </FormSection>
            </div>
          </section>

          <section className="gema-panel p-6">
            <div className="admin-form">
              <FormSection label="Ítems de la cotización">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="min-w-0 flex-1 sm:min-w-[12rem]">
                    <Select
                      value={addProductId}
                      onChange={(e) => setAddProductId(e.target.value)}
                    >
                      <option value="">Seleccionar producto…</option>
                      {products.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <button type="button" className="btn-secondary shrink-0" onClick={addLine}>
                    Agregar
                  </button>
                </div>

                <div className="space-y-3">
                  {lines.map((line, index) => {
                    const product = products.find((p) => p.id === line.product_id);
                    return (
                      <div key={line.key} className="admin-line-item">
                        <p className="admin-line-item-title">{product?.name ?? "Producto"}</p>
                        <div className="admin-form-row">
                      <FormField label="Tier">
                        <Select
                          value={line.tier}
                          onChange={(e) => {
                            const tier = e.target.value as LineDraft["tier"];
                            setLines((prev) =>
                              prev.map((l, i) => (i === index ? { ...l, tier } : l)),
                            );
                          }}
                        >
                          <option value="min">Mínimo</option>
                          <option value="rec">Recomendado</option>
                          <option value="high">Alto</option>
                          <option value="manual">Manual</option>
                        </Select>
                      </FormField>
                      <FormField label="Cantidad">
                        <Input
                          type="number"
                          min={1}
                          value={line.quantity}
                          onChange={(e) => {
                            const quantity = parseInt(e.target.value, 10) || 1;
                            setLines((prev) =>
                              prev.map((l, i) => (i === index ? { ...l, quantity } : l)),
                            );
                          }}
                        />
                      </FormField>
                      {line.tier === "manual" ? (
                        <FormField label="Precio manual">
                          <Input
                            type="number"
                            step="0.01"
                            min="0"
                            value={line.manual_price}
                            onChange={(e) => {
                              setLines((prev) =>
                                prev.map((l, i) =>
                                  i === index ? { ...l, manual_price: e.target.value } : l,
                                ),
                              );
                            }}
                          />
                        </FormField>
                      ) : (
                        <FormField label="P. unitario">
                          <Input
                            readOnly
                            value={
                              product
                                ? formatUsd(
                                    unitPriceFor(product, line.tier, line.manual_price).toFixed(4),
                                  )
                                : "—"
                            }
                          />
                        </FormField>
                      )}
                    </div>
                    <button
                      type="button"
                      className="btn-ghost btn-sm mt-2 text-error"
                      onClick={() => setLines((prev) => prev.filter((_, i) => i !== index))}
                    >
                      Quitar ítem
                    </button>
                  </div>
                );
              })}
                </div>

                <FormField label="IVA (%)" className="max-w-[120px]">
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    max={100}
                    className="mono-input"
                    value={ivaPct}
                    onChange={(e) => setIvaPct(parseFloat(e.target.value) || 0)}
                  />
                </FormField>
              </FormSection>
            </div>
          </section>

          <button type="button" className="btn-primary" disabled={saving} onClick={() => void save()}>
            {saving ? "Guardando…" : "Guardar cotización"}
          </button>
        </div>

        <section className="gema-panel sticky top-20 h-fit p-6">
          <span className="admin-form-section-label mb-4">Vista previa</span>
          <p className="mb-1 text-xs uppercase tracking-wide text-secondary">Proforma</p>
          <p className="font-display mb-4 text-xl font-bold text-primary">Nueva cotización</p>

          <p className="mb-4 text-sm">
            <strong>Cliente:</strong> {client.client_name || "—"}
          </p>

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
                {previewLines.map((line, i) => (
                  <tr key={i}>
                    <td>{line.name}</td>
                    <td>{tierLabel(line.tier)}</td>
                    <td>{line.quantity}</td>
                    <td>{formatUsd(line.unitPrice)}</td>
                    <td>{formatUsd(line.lineTotal)}</td>
                  </tr>
                ))}
                {!previewLines.length ? (
                  <tr>
                    <td colSpan={5} className="text-secondary">
                      Agrega productos para ver la vista previa.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          <div className="space-y-1 border-t border-border pt-4 text-sm">
            <div className="flex justify-between">
              <span>Subtotal</span>
              <span>{formatUsd(totals.subtotal)}</span>
            </div>
            <div className="flex justify-between">
              <span>IVA ({ivaPct}%)</span>
              <span>{formatUsd(totals.iva)}</span>
            </div>
            <div className="flex justify-between text-base font-semibold">
              <span>Total</span>
              <span>{formatUsd(totals.total)}</span>
            </div>
          </div>
        </section>
      </div>
    </AdminShell>
  );
}
