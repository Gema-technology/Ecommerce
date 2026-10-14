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
  suppliersApi,
  type ProductSuppliersResponse,
  type Supplier,
  type SupplierAvailability,
} from "@/lib/suppliers-api";

const AVAILABILITIES: SupplierAvailability[] = [
  "IN_STOCK",
  "LOW_STOCK",
  "OUT_OF_STOCK",
  "PREORDER",
  "UNKNOWN",
];

const LINK_FORM_ID = "product-supplier-link-form";

export function ProductSuppliersPanel({ productId }: { productId: string }) {
  const [data, setData] = useState<ProductSuppliersResponse | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    supplier_id: "",
    supplier_sku: "",
    cost: "",
    availability: "UNKNOWN" as SupplierAvailability,
    lead_time_days: "",
  });

  async function refresh() {
    const [linked, all] = await Promise.all([
      suppliersApi.listForProduct(productId),
      suppliersApi.list({ is_active: true, page: 1, page_size: 100 }),
    ]);
    setData(linked);
    setSuppliers(all.items);
  }

  useEffect(() => {
    void (async () => {
      await refresh();
    })().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Error al cargar proveedores");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  function openAdd() {
    setForm({
      supplier_id: "",
      supplier_sku: "",
      cost: "",
      availability: "UNKNOWN",
      lead_time_days: "",
    });
    setModalOpen(true);
  }

  async function onAdd(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await suppliersApi.linkToProduct(productId, {
        supplier_id: form.supplier_id,
        supplier_sku: form.supplier_sku || null,
        cost: form.cost,
        currency: "USD",
        availability: form.availability,
        lead_time_days: form.lead_time_days ? Number(form.lead_time_days) : null,
      });
      setModalOpen(false);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo asociar");
    } finally {
      setSaving(false);
    }
  }

  async function deactivate(supplierId: string, supplierProductId: string) {
    setError(null);
    try {
      await suppliersApi.removeProduct(supplierId, supplierProductId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo desactivar");
    }
  }

  return (
    <section className="mt-12 border-t border-border pt-8">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">Proveedores</h2>
        <button type="button" className="btn-primary" onClick={openAdd}>
          <Plus className="h-4 w-4" aria-hidden />
          Agregar proveedor
        </button>
      </div>
      {error ? <p className="mb-3 text-sm font-medium text-error">{error}</p> : null}

      <div className="overflow-x-auto border border-border">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-surface-elevated">
            <tr>
              <th className="px-3 py-2 font-medium">Proveedor</th>
              <th className="px-3 py-2 font-medium">Costo</th>
              <th className="px-3 py-2 font-medium">Moneda</th>
              <th className="px-3 py-2 font-medium">Disponibilidad</th>
              <th className="px-3 py-2 font-medium">Plazo (días)</th>
              <th className="px-3 py-2 font-medium">SKU proveedor</th>
              <th className="px-3 py-2 font-medium">Última revisión</th>
              <th className="px-3 py-2 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {(data?.suppliers ?? []).map((item) => (
              <tr key={item.supplier_product_id} className="border-b border-border">
                <td className="px-3 py-2">{item.supplier_name}</td>
                <td className="px-3 py-2">{item.cost}</td>
                <td className="px-3 py-2">{item.currency}</td>
                <td className="px-3 py-2">{item.availability}</td>
                <td className="px-3 py-2">{item.lead_time_days ?? "—"}</td>
                <td className="px-3 py-2 font-mono text-xs">{item.supplier_sku ?? "—"}</td>
                <td className="px-3 py-2 text-xs">
                  {item.last_checked_at
                    ? new Date(item.last_checked_at).toLocaleString()
                    : "—"}
                </td>
                <td className="px-3 py-2">
                  {item.is_active ? (
                    <button
                      type="button"
                      className="btn-ghost btn-sm"
                      onClick={() =>
                        void deactivate(item.supplier_id, item.supplier_product_id)
                      }
                    >
                      Desactivar
                    </button>
                  ) : (
                    <span className="text-muted">Inactivo</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <FormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Agregar proveedor"
        subtitle="Asocia un proveedor a este producto"
        footer={
          <FormModalActions
            formId={LINK_FORM_ID}
            submitLabel="Agregar proveedor"
            saving={saving}
            onCancel={() => setModalOpen(false)}
          />
        }
      >
        <form
          id={LINK_FORM_ID}
          className="admin-form"
          onSubmit={(e) => void onAdd(e)}
        >
          <FormSection label="Proveedor">
            <div>
              <label className="label-field" htmlFor="supplier_id">
                Proveedor
              </label>
              <Select
                id="supplier_id"
                required
                value={form.supplier_id}
                onChange={(e) => setForm((prev) => ({ ...prev, supplier_id: e.target.value }))}
              >
                <option value="">Seleccionar…</option>
                {suppliers.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.commercial_name || s.business_name}
                  </option>
                ))}
              </Select>
            </div>
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="ps_sku">
                  Supplier SKU
                </label>
                <input
                  id="ps_sku"
                  className="input-field"
                  value={form.supplier_sku}
                  onChange={(e) => setForm((prev) => ({ ...prev, supplier_sku: e.target.value }))}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="ps_cost">
                  Cost (USD)
                </label>
                <input
                  id="ps_cost"
                  className="input-field"
                  required
                  value={form.cost}
                  onChange={(e) => setForm((prev) => ({ ...prev, cost: e.target.value }))}
                />
              </div>
            </FieldRow>
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="ps_avail">
                  Availability
                </label>
                <Select
                  id="ps_avail"
                  value={form.availability}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      availability: e.target.value as SupplierAvailability,
                    }))
                  }
                >
                  {AVAILABILITIES.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="label-field" htmlFor="ps_lead">
                  Lead time (days)
                </label>
                <input
                  id="ps_lead"
                  className="input-field"
                  value={form.lead_time_days}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, lead_time_days: e.target.value }))
                  }
                />
              </div>
            </FieldRow>
          </FormSection>
        </form>
      </FormModal>
    </section>
  );
}
