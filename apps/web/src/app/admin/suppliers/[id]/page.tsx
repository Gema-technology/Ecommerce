"use client";

import { Pencil, Plus } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import {
  FieldRow,
  FormModal,
  FormModalActions,
  FormSection,
} from "@/components/admin/forms/AdminFormPrimitives";
import { SupplierForm, SUPPLIER_FORM_ID } from "@/components/admin/SupplierForm";
import { AppLoading } from "@/components/shared/AppLoading";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Product } from "@/lib/catalog-api";
import {
  suppliersApi,
  type Supplier,
  type SupplierAvailability,
  type SupplierProduct,
} from "@/lib/suppliers-api";

const AVAILABILITIES: SupplierAvailability[] = [
  "IN_STOCK",
  "LOW_STOCK",
  "OUT_OF_STOCK",
  "PREORDER",
  "UNKNOWN",
];

const LINK_FORM_ID = "supplier-link-form";

export default function SupplierDetailPage() {
  const params = useParams<{ id: string }>();
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [products, setProducts] = useState<SupplierProduct[]>([]);
  const [catalog, setCatalog] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [linkOpen, setLinkOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [linkSaving, setLinkSaving] = useState(false);
  const [link, setLink] = useState({
    product_id: "",
    supplier_sku: "",
    supplier_product_name: "",
    cost: "",
    availability: "UNKNOWN" as SupplierAvailability,
    lead_time_days: "",
    minimum_order_quantity: "1",
    supplier_url: "",
  });

  async function refresh() {
    const [s, sps, catalogList] = await Promise.all([
      suppliersApi.get(params.id),
      suppliersApi.listProducts(params.id),
      catalogApi.listProducts({ page_size: 100 }, true),
    ]);
    setSupplier(s);
    setProducts(sps);
    setCatalog(catalogList.items.filter((p) => p.is_active));
  }

  useEffect(() => {
    void (async () => {
      await refresh();
    })().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.id]);

  function resetLink() {
    setLink({
      product_id: "",
      supplier_sku: "",
      supplier_product_name: "",
      cost: "",
      availability: "UNKNOWN",
      lead_time_days: "",
      minimum_order_quantity: "1",
      supplier_url: "",
    });
  }

  async function onLink(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLinkSaving(true);
    try {
      await suppliersApi.addProduct(params.id, {
        product_id: link.product_id,
        supplier_sku: link.supplier_sku || null,
        supplier_product_name: link.supplier_product_name || null,
        cost: link.cost,
        currency: "USD",
        availability: link.availability,
        lead_time_days: link.lead_time_days ? Number(link.lead_time_days) : null,
        minimum_order_quantity: Number(link.minimum_order_quantity || 1),
        supplier_url: link.supplier_url || null,
      });
      resetLink();
      setLinkOpen(false);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo asociar");
    } finally {
      setLinkSaving(false);
    }
  }

  async function toggleProduct(item: SupplierProduct) {
    if (item.is_active) {
      const ok = await confirm({
        title: "Desactivar vínculo",
        description: `¿Desactivar el producto «${item.supplier_product_name || item.supplier_sku}» de este proveedor?`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setError(null);
    try {
      if (item.is_active) {
        await suppliersApi.removeProduct(params.id, item.id);
        toast.success("Vínculo desactivado.");
      } else {
        await suppliersApi.updateProduct(params.id, item.id, { is_active: true });
        toast.success("Vínculo activado.");
      }
      await refresh();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo actualizar";
      setError(msg);
      toast.error(msg);
    }
  }

  if (!supplier && !error) {
    return (
      <AdminShell title="Proveedor">
        <AppLoading compact label="Cargando proveedor" hideHint className="!py-12" />
      </AdminShell>
    );
  }

  return (
    <AdminShell title={supplier?.commercial_name || supplier?.business_name || "Proveedor"}>
      {confirmDialog}
      {error ? <p className="mb-4 text-sm font-medium text-error">{error}</p> : null}

      {supplier ? (
        <>
          <section className="mb-10">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold">Información general</h2>
              <button type="button" className="btn-secondary btn-sm" onClick={() => setEditOpen(true)}>
                <Pencil className="h-3 w-3" aria-hidden />
                Editar
              </button>
            </div>

            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <Item label="Razón social" value={supplier.business_name} />
              <Item label="Comercial" value={supplier.commercial_name} />
              <Item label="Tax ID" value={`${supplier.tax_id_type}: ${supplier.tax_id}`} />
              <Item label="Correo" value={supplier.email} />
              <Item label="Teléfono" value={supplier.phone} />
              <Item label="Website" value={supplier.website_url} />
              <Item label="Contacto" value={supplier.contact_name} />
              <Item label="Dirección" value={supplier.address} />
              <Item label="Ciudad" value={supplier.city} />
              <Item label="Provincia" value={supplier.province} />
              <Item label="País" value={supplier.country} />
              <Item label="Estado" value={supplier.is_active ? "Activo" : "Inactivo"} />
            </dl>
          </section>

          <section>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold">Productos ofrecidos</h2>
              <button
                type="button"
                className="btn-primary"
                onClick={() => {
                  resetLink();
                  setLinkOpen(true);
                }}
              >
                <Plus className="h-4 w-4" aria-hidden />
                Asociar producto
              </button>
            </div>

            <div className="gema-panel overflow-x-auto">
              <table className="gema-table">
                <thead>
                  <tr>
                    <th>Producto</th>
                    <th>SKU prov.</th>
                    <th>Costo</th>
                    <th>Disponibilidad</th>
                    <th>Lead</th>
                    <th>Estado</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((p) => (
                    <tr key={p.id}>
                      <td>
                        {p.product_sku} — {p.product_name}
                      </td>
                      <td className="font-mono text-xs">{p.supplier_sku ?? "—"}</td>
                      <td>
                        {p.currency} {p.cost}
                      </td>
                      <td>{p.availability}</td>
                      <td>{p.lead_time_days ?? "—"}</td>
                      <td>{p.is_active ? "Activo" : "Inactivo"}</td>
                      <td>
                        <button
                          type="button"
                          className="btn-ghost btn-sm"
                          onClick={() => void toggleProduct(p)}
                        >
                          {p.is_active ? "Desactivar" : "Activar"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <FormModal
            open={editOpen}
            onClose={() => setEditOpen(false)}
            size="lg"
            title="Editar proveedor"
            subtitle={supplier.tax_id}
            footer={
              <FormModalActions
                formId={SUPPLIER_FORM_ID}
                submitLabel="Guardar cambios"
                saving={saving}
                onCancel={() => setEditOpen(false)}
              />
            }
          >
            <SupplierForm
              key={supplier.id}
              supplier={supplier}
              onSavingChange={setSaving}
              onSuccess={async () => {
                setEditOpen(false);
                await refresh();
              }}
            />
          </FormModal>

          <FormModal
            open={linkOpen}
            onClose={() => setLinkOpen(false)}
            size="lg"
            title="Asociar producto"
            subtitle="Vincular un producto del catálogo a este proveedor"
            footer={
              <FormModalActions
                formId={LINK_FORM_ID}
                submitLabel="Asociar producto"
                saving={linkSaving}
                onCancel={() => setLinkOpen(false)}
              />
            }
          >
            <form
              id={LINK_FORM_ID}
              className="admin-form"
              onSubmit={(e) => void onLink(e)}
            >
              <FormSection label="Producto">
                <div>
                  <label className="label-field" htmlFor="product_id">
                    Producto existente
                  </label>
                  <Select
                    id="product_id"
                    required
                    value={link.product_id}
                    onChange={(e) => setLink((prev) => ({ ...prev, product_id: e.target.value }))}
                  >
                    <option value="">Seleccionar…</option>
                    {catalog.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.sku} — {p.name}
                      </option>
                    ))}
                  </Select>
                </div>
                <div>
                  <label className="label-field" htmlFor="supplier_product_name">
                    Nombre en proveedor
                  </label>
                  <input
                    id="supplier_product_name"
                    className="input-field"
                    value={link.supplier_product_name}
                    onChange={(e) =>
                      setLink((prev) => ({ ...prev, supplier_product_name: e.target.value }))
                    }
                  />
                </div>
              </FormSection>
              <FormSection label="Comercial">
                <FieldRow>
                  <div>
                    <label className="label-field" htmlFor="supplier_sku">
                      SKU proveedor
                    </label>
                    <input
                      id="supplier_sku"
                      className="input-field"
                      value={link.supplier_sku}
                      onChange={(e) =>
                        setLink((prev) => ({ ...prev, supplier_sku: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="label-field" htmlFor="cost">
                      Costo (USD)
                    </label>
                    <input
                      id="cost"
                      className="input-field"
                      required
                      value={link.cost}
                      onChange={(e) => setLink((prev) => ({ ...prev, cost: e.target.value }))}
                    />
                  </div>
                </FieldRow>
                <FieldRow className="sm:grid-cols-3">
                  <div>
                    <label className="label-field" htmlFor="availability">
                      Disponibilidad
                    </label>
                    <Select
                      id="availability"
                      value={link.availability}
                      onChange={(e) =>
                        setLink((prev) => ({
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
                    <label className="label-field" htmlFor="lead_time_days">
                      Lead time (días)
                    </label>
                    <input
                      id="lead_time_days"
                      className="input-field"
                      value={link.lead_time_days}
                      onChange={(e) =>
                        setLink((prev) => ({ ...prev, lead_time_days: e.target.value }))
                      }
                    />
                  </div>
                  <div>
                    <label className="label-field" htmlFor="moq">
                      MOQ
                    </label>
                    <input
                      id="moq"
                      className="input-field"
                      value={link.minimum_order_quantity}
                      onChange={(e) =>
                        setLink((prev) => ({
                          ...prev,
                          minimum_order_quantity: e.target.value,
                        }))
                      }
                    />
                  </div>
                </FieldRow>
                <div>
                  <label className="label-field" htmlFor="supplier_url">
                    URL proveedor
                  </label>
                  <input
                    id="supplier_url"
                    className="input-field"
                    value={link.supplier_url}
                    onChange={(e) =>
                      setLink((prev) => ({ ...prev, supplier_url: e.target.value }))
                    }
                  />
                </div>
              </FormSection>
            </form>
          </FormModal>
        </>
      ) : null}
    </AdminShell>
  );
}

function Item({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div>
      <dt className="text-muted">{label}</dt>
      <dd className="text-foreground">{value || "—"}</dd>
    </div>
  );
}
