"use client";

import { Plus } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import {
  FieldRow,
  FormModal,
  FormModalActions,
  FormSection,
} from "@/components/admin/forms/AdminFormPrimitives";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/auth-api";
import {
  pricingApi,
  type MarginResult,
  type PriceType,
  type ProductPrice,
} from "@/lib/pricing-api";
import { suppliersApi, type ProductSuppliersResponse } from "@/lib/suppliers-api";

const PRICE_FORM_ID = "product-price-form";

export function ProductPricingPanel({ productId }: { productId: string }) {
  const [current, setCurrent] = useState<ProductPrice | null>(null);
  const [history, setHistory] = useState<ProductPrice[]>([]);
  const [suppliers, setSuppliers] = useState<ProductSuppliersResponse | null>(null);
  const [margin, setMargin] = useState<MarginResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    price_type: "RETAIL" as PriceType,
    amount: "",
    starts_at: "",
    ends_at: "",
    supplier_product_id: "",
  });

  async function refresh() {
    const [cur, hist, linked] = await Promise.all([
      pricingApi.current(productId),
      pricingApi.history(productId),
      suppliersApi.listForProduct(productId),
    ]);
    setCurrent(cur);
    setHistory(hist);
    setSuppliers(linked);
    try {
      const m = await pricingApi.margin(
        productId,
        form.supplier_product_id || undefined,
      );
      setMargin(m);
    } catch {
      setMargin(null);
    }
  }

  useEffect(() => {
    void (async () => {
      await refresh();
    })().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Error al cargar precios");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  function openCreate() {
    setForm({
      price_type: "RETAIL",
      amount: "",
      starts_at: "",
      ends_at: "",
      supplier_product_id: "",
    });
    setModalOpen(true);
  }

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await pricingApi.create(productId, {
        price_type: form.price_type,
        amount: form.amount,
        currency: "USD",
        starts_at: form.starts_at
          ? new Date(form.starts_at).toISOString()
          : undefined,
        ends_at: form.ends_at ? new Date(form.ends_at).toISOString() : null,
        supplier_product_id: form.supplier_product_id || null,
      });
      setModalOpen(false);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el precio");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(price: ProductPrice) {
    setError(null);
    try {
      if (price.is_active) {
        await pricingApi.deactivate(productId, price.id);
      } else {
        await pricingApi.update(productId, price.id, { is_active: true });
      }
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar");
    }
  }

  return (
    <section className="mt-12 border-t border-border pt-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Precios</h2>
        <button type="button" className="btn-primary" onClick={openCreate}>
          <Plus className="h-4 w-4" aria-hidden />
          Crear precio
        </button>
      </div>
      {error ? <p className="mb-3 text-sm font-medium text-error">{error}</p> : null}

      <div className="mb-6 grid gap-3 text-sm sm:grid-cols-2">
        <div className="border border-border p-4">
          <p className="text-muted">Precio de venta actual</p>
          <p className="mt-1 text-xl font-semibold">
            {current
              ? `${current.currency} ${current.amount}`
              : "Sin precio vigente"}
          </p>
        </div>
        <div className="border border-border p-4">
          <p className="text-muted">Margen</p>
          {margin ? (
            <>
              <p className="mt-1">
                Costo: {margin.cost} ({margin.cost_source ?? "referencia"})
              </p>
              <p>
                Margen: {margin.margin_amount}
                {margin.margin_percentage != null
                  ? ` (${margin.margin_percentage}%)`
                  : ""}
              </p>
            </>
          ) : (
            <p className="mt-1 text-secondary">No disponible</p>
          )}
        </div>
      </div>

      <h3 className="mb-3 font-semibold">Historial de precios</h3>
      <div className="overflow-x-auto border border-border">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-surface-elevated">
            <tr>
              <th className="px-3 py-2 font-medium">Tipo</th>
              <th className="px-3 py-2 font-medium">Monto</th>
              <th className="px-3 py-2 font-medium">Inicio</th>
              <th className="px-3 py-2 font-medium">Fin</th>
              <th className="px-3 py-2 font-medium">Estado</th>
              <th className="px-3 py-2 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {history.map((p) => (
              <tr key={p.id} className="border-b border-border">
                <td className="px-3 py-2">{p.price_type}</td>
                <td className="px-3 py-2">
                  {p.currency} {p.amount}
                </td>
                <td className="px-3 py-2 text-xs">
                  {new Date(p.starts_at).toLocaleString()}
                </td>
                <td className="px-3 py-2 text-xs">
                  {p.ends_at ? new Date(p.ends_at).toLocaleString() : "—"}
                </td>
                <td className="px-3 py-2">{p.is_active ? "Activo" : "Inactivo"}</td>
                <td className="px-3 py-2">
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    onClick={() => void toggleActive(p)}
                  >
                    {p.is_active ? "Desactivar" : "Activar"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Crear precio"
        subtitle="Define un precio vigente para este producto"
        footer={
          <FormModalActions
            formId={PRICE_FORM_ID}
            submitLabel="Crear precio"
            saving={saving}
            onCancel={() => setModalOpen(false)}
          />
        }
      >
        <form
          id={PRICE_FORM_ID}
          className="admin-form"
          onSubmit={(e) => void onCreate(e)}
        >
          <FormSection label="Precio">
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="price_type">
                  Price type
                </label>
                <Select
                  id="price_type"
                  value={form.price_type}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, price_type: e.target.value as PriceType }))
                  }
                >
                  <option value="RETAIL">RETAIL</option>
                  <option value="WHOLESALE">WHOLESALE</option>
                  <option value="PROMOTIONAL">PROMOTIONAL</option>
                </Select>
              </div>
              <div>
                <label className="label-field" htmlFor="amount">
                  Amount (USD)
                </label>
                <input
                  id="amount"
                  className="input-field"
                  required
                  value={form.amount}
                  onChange={(e) => setForm((prev) => ({ ...prev, amount: e.target.value }))}
                />
              </div>
            </FieldRow>
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="starts_at">
                  Starts at
                </label>
                <input
                  id="starts_at"
                  type="datetime-local"
                  className="input-field"
                  value={form.starts_at}
                  onChange={(e) => setForm((prev) => ({ ...prev, starts_at: e.target.value }))}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="ends_at">
                  Ends at
                </label>
                <input
                  id="ends_at"
                  type="datetime-local"
                  className="input-field"
                  value={form.ends_at}
                  onChange={(e) => setForm((prev) => ({ ...prev, ends_at: e.target.value }))}
                />
              </div>
            </FieldRow>
            <div>
              <label className="label-field" htmlFor="supplier_product_id">
                Cost source (SupplierProduct)
              </label>
              <Select
                id="supplier_product_id"
                value={form.supplier_product_id}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, supplier_product_id: e.target.value }))
                }
              >
                <option value="">Sin referencia / seleccionar</option>
                {(suppliers?.suppliers ?? [])
                  .filter((s) => s.is_active)
                  .map((s) => (
                    <option key={s.supplier_product_id} value={s.supplier_product_id}>
                      {s.supplier_name} — cost {s.cost} {s.currency}
                    </option>
                  ))}
              </Select>
            </div>
          </FormSection>
        </form>
      </FormModal>
    </section>
  );
}
