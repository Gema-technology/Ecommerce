"use client";

import { Plus, Settings2 } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import {
  FieldRow,
  FormModal,
  FormModalActions,
  FormSection,
  PriceInput,
} from "@/components/admin/forms/AdminFormPrimitives";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import {
  formatUsd,
  marginToPercent,
  percentToMargin,
  quotesApi,
  type PricingConfig,
  type QuoteProduct,
} from "@/lib/quotes-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

const MARGINS_FORM_ID = "catalog-margins-form";

type ProductForm = {
  name: string;
  category: string;
  cost_price: string;
  other_costs: string;
};

const emptyProduct: ProductForm = {
  name: "",
  category: "",
  cost_price: "",
  other_costs: "0",
};

export default function AdminCatalogoPage() {
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const list = useAdminListParams();
  const activeOnly = list.get("active");
  const [config, setConfig] = useState<PricingConfig | null>(null);
  const [products, setProducts] = useState<QuoteProduct[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingConfig, setSavingConfig] = useState(false);
  const [form, setForm] = useState<ProductForm>(emptyProduct);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [marginsOpen, setMarginsOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draftQ, setDraftQ] = useState(list.q);
  const [draftActive, setDraftActive] = useState(activeOnly);
  const [draftMargins, setDraftMargins] = useState({
    min: "",
    rec: "",
    high: "",
    card: "",
    iva: "",
  });

  useEffect(() => {
    setDraftQ(list.q);
    setDraftActive(activeOnly);
  }, [list.q, activeOnly]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cfg, catalog] = await Promise.all([
        quotesApi.getPricingConfig(),
        quotesApi.listProducts({
          q: list.q || undefined,
          page: list.page,
          page_size: list.pageSize,
          active_only: activeOnly === "true",
        }),
      ]);
      setConfig(cfg);
      setProducts(catalog.items);
      setTotal(catalog.total);
      setTotalPages(catalog.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
      setProducts([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, activeOnly]);

  useEffect(() => {
    void load();
  }, [load]);

  const marginFields = useMemo(() => {
    if (!config) return null;
    return {
      min: marginToPercent(config.min_margin),
      rec: marginToPercent(config.rec_margin),
      high: marginToPercent(config.high_margin),
      card: marginToPercent(config.card_cost),
      iva: marginToPercent(config.default_iva),
    };
  }, [config]);

  function openMargins() {
    if (!marginFields) return;
    setDraftMargins({
      min: String(marginFields.min),
      rec: String(marginFields.rec),
      high: String(marginFields.high),
      card: String(marginFields.card),
      iva: String(marginFields.iva),
    });
    setMarginsOpen(true);
  }

  async function saveMargins(event: FormEvent) {
    event.preventDefault();
    setSavingConfig(true);
    setError(null);
    try {
      const updated = await quotesApi.updatePricingConfig({
        min_margin: percentToMargin(parseFloat(draftMargins.min)),
        rec_margin: percentToMargin(parseFloat(draftMargins.rec)),
        high_margin: percentToMargin(parseFloat(draftMargins.high)),
        card_cost: percentToMargin(parseFloat(draftMargins.card)),
        default_iva: percentToMargin(parseFloat(draftMargins.iva)),
      });
      setConfig(updated);
      const catalog = await quotesApi.listProducts({ page_size: 100 });
      setProducts(catalog.items);
      setMarginsOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setSavingConfig(false);
    }
  }

  function openCreate() {
    setEditingId(null);
    setForm(emptyProduct);
    setModalOpen(true);
  }

  function openEdit(product: QuoteProduct) {
    setEditingId(product.id);
    setForm({
      name: product.name,
      category: product.category ?? "",
      cost_price: product.cost_price,
      other_costs: product.other_costs,
    });
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingId(null);
    setForm(emptyProduct);
  }

  async function saveProduct(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editingId) {
        await quotesApi.updateProduct(editingId, {
          name: form.name,
          category: form.category || null,
          cost_price: form.cost_price,
          other_costs: form.other_costs,
        });
      } else {
        await quotesApi.createProduct({
          name: form.name,
          category: form.category || null,
          cost_price: form.cost_price,
          other_costs: form.other_costs,
        });
      }
      closeModal();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar producto");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(product: QuoteProduct) {
    if (product.is_active) {
      const ok = await confirm({
        title: "Desactivar ítem",
        description: `¿Desactivar «${product.name}» del catálogo de cotización?`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setError(null);
    try {
      await quotesApi.updateProduct(product.id, { is_active: !product.is_active });
      await load();
      toast.success(
        product.is_active ? "Ítem desactivado." : "Ítem activado.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo actualizar";
      setError(msg);
      toast.error(msg);
    }
  }

  const saveLabel = editingId ? "Guardar cambios" : "Agregar producto";

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      q: draftQ,
      active: draftActive,
    });
  }

  return (
    <AdminShell title="Catálogo de cotización">
      {confirmDialog}

      {marginFields ? (
        <p className="mb-4 text-xs text-secondary">
          Márgenes: min {marginFields.min}% · rec {marginFields.rec}% · alto{" "}
          {marginFields.high}%
        </p>
      ) : null}

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftActive("");
          list.clearFilters(["q", "active"]);
        }}
        actions={
          <>
            {config && marginFields ? (
              <button
                type="button"
                className="btn-secondary"
                onClick={openMargins}
              >
                <Settings2 className="h-4 w-4" aria-hidden />
                Márgenes
              </button>
            ) : null}
            <button type="button" className="btn-primary" onClick={openCreate}>
              <Plus className="h-4 w-4" aria-hidden />
              Nuevo producto
            </button>
          </>
        }
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Nombre o categoría"
          />
        </FormField>
        <FormField label="Estado" className="w-40 min-w-0">
          <Select
            value={draftActive}
            onChange={(e) => setDraftActive(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="true">Solo activos</option>
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={8}
        loading={loading}
        error={error}
        isEmpty={!products.length}
        emptyMessage="No hay productos en el catálogo de cotización."
        meta={`${total} ítem${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>Producto</th>
            <th>Categoría</th>
            <th>Costo real</th>
            <th>P. mínimo</th>
            <th>P. recomendado</th>
            <th>P. alto</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/catalogo"
          />
        }
      >
        {products.map((p) => (
          <tr key={p.id}>
            <td className="font-medium">{p.name}</td>
            <td>
              {p.category ? (
                <span className="font-mono rounded-full border border-border px-2 py-0.5 text-[10.5px] text-secondary">
                  {p.category}
                </span>
              ) : (
                "-"
              )}
            </td>
            <td className="font-mono text-xs">{formatUsd(p.cost_real)}</td>
            <td className="font-mono text-xs">{formatUsd(p.price_min)}</td>
            <td className="font-mono text-xs">{formatUsd(p.price_rec)}</td>
            <td className="font-mono text-xs">{formatUsd(p.price_high)}</td>
            <td>{p.is_active ? "Activo" : "Inactivo"}</td>
            <td>
              <button
                type="button"
                className="btn-ghost btn-sm mr-2"
                onClick={() => openEdit(p)}
              >
                Editar
              </button>
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
      </AdminTable>

      <FormModal
        open={modalOpen}
        onClose={closeModal}
        title={editingId ? "Editar producto" : "Nuevo producto"}
        subtitle="Catálogo de cotización — costos y márgenes"
        footer={
          <FormModalActions
            formId="catalog-product-form"
            submitLabel={saveLabel}
            saving={saving}
            onCancel={closeModal}
          />
        }
      >
        <form
          id="catalog-product-form"
          className="admin-form"
          onSubmit={(e) => void saveProduct(e)}
        >
          <FormSection label="Información general">
            <FormField label="Nombre del producto" required>
              <Input
                required
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Ej. Laptop Vektor 14 Pro"
              />
            </FormField>
            <FormField label="Categoría">
              <Input
                value={form.category}
                onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                placeholder="Computo, Audio..."
              />
            </FormField>
          </FormSection>

          <FormSection label="Costos">
            <FieldRow>
              <FormField label="Costo de compra" required>
                <PriceInput
                  required
                  value={form.cost_price}
                  onChange={(cost_price) => setForm((f) => ({ ...f, cost_price }))}
                />
              </FormField>
              <FormField label="Otros costos">
                <PriceInput
                  value={form.other_costs}
                  onChange={(other_costs) => setForm((f) => ({ ...f, other_costs }))}
                />
              </FormField>
            </FieldRow>
            <p className="admin-form-hint">
              El costo real y los tres precios (min / rec / alto) se calculan con los márgenes
              globales.
            </p>
          </FormSection>
        </form>
      </FormModal>

      <FormModal
        open={marginsOpen}
        onClose={() => setMarginsOpen(false)}
        size="lg"
        title="Márgenes globales"
        subtitle="Al guardar, los precios de la tabla se recalculan"
        footer={
          <FormModalActions
            formId={MARGINS_FORM_ID}
            submitLabel="Guardar márgenes"
            saving={savingConfig}
            onCancel={() => setMarginsOpen(false)}
          />
        }
      >
        <form
          id={MARGINS_FORM_ID}
          className="admin-form"
          onSubmit={(e) => void saveMargins(e)}
        >
          <FormSection label="Porcentajes">
            <div className="admin-form-row !grid-cols-2 lg:!grid-cols-3">
              {(
                [
                  ["min", "Mínimo (%)"],
                  ["rec", "Recomendado (%)"],
                  ["high", "Alto (%)"],
                  ["card", "Costo tarjeta (%)"],
                  ["iva", "IVA default (%)"],
                ] as const
              ).map(([key, label]) => (
                <FormField key={key} label={label}>
                  <Input
                    type="number"
                    step="0.1"
                    min={0}
                    max={99}
                    className="mono-input"
                    required
                    value={draftMargins[key]}
                    onChange={(e) =>
                      setDraftMargins((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </FormField>
              ))}
            </div>
          </FormSection>
        </form>
      </FormModal>
    </AdminShell>
  );
}
