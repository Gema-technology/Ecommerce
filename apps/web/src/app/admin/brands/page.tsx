"use client";

import { Pencil, Plus } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { BrandForm, BRAND_FORM_ID } from "@/components/admin/BrandForm";
import {
  FormModal,
  FormModalActions,
} from "@/components/admin/forms/AdminFormPrimitives";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Brand } from "@/lib/catalog-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

export default function AdminBrandsPage() {
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const list = useAdminListParams();
  const active = list.get("active");

  const [items, setItems] = useState<Brand[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Brand | null>(null);
  const [saving, setSaving] = useState(false);

  const [draftQ, setDraftQ] = useState(list.q);
  const [draftActive, setDraftActive] = useState(active);

  useEffect(() => {
    setDraftQ(list.q);
    setDraftActive(active);
  }, [list.q, active]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await catalogApi.listBrandsAdmin({
        page: list.page,
        page_size: list.pageSize,
        q: list.q || undefined,
        is_active:
          active === "true" ? true : active === "false" ? false : undefined,
      });
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
      setItems([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, active]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      q: draftQ,
      active: draftActive,
    });
  }

  function openCreate() {
    setEditing(null);
    setModalOpen(true);
  }

  function openEdit(brand: Brand) {
    setEditing(brand);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditing(null);
  }

  async function toggleActive(brand: Brand) {
    if (brand.is_active) {
      const ok = await confirm({
        title: "Desactivar marca",
        description: `¿Desactivar «${brand.name}»?`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setError(null);
    try {
      if (brand.is_active) {
        await catalogApi.deleteBrand(brand.id);
        toast.success("Marca desactivada.");
      } else {
        await catalogApi.updateBrand(brand.id, { is_active: true });
        toast.success("Marca activada.");
      }
      await load();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo actualizar";
      setError(msg);
      toast.error(msg);
    }
  }

  return (
    <AdminShell title="Marcas">
      {confirmDialog}

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftActive("");
          list.clearFilters(["q", "active"]);
        }}
        actions={
          <button type="button" className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Nueva marca
          </button>
        }
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Nombre o slug"
          />
        </FormField>
        <FormField label="Estado" className="w-36 min-w-0">
          <Select
            value={draftActive}
            onChange={(e) => setDraftActive(e.target.value)}
          >
            <option value="">Todas</option>
            <option value="true">Activas</option>
            <option value="false">Inactivas</option>
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={6}
        loading={loading}
        error={error}
        isEmpty={!items.length}
        emptyMessage="No hay marcas."
        meta={`${total} marca${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>Logo</th>
            <th>Nombre</th>
            <th>Slug</th>
            <th>Categorías</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/brands"
          />
        }
      >
        {items.map((item) => (
          <tr key={item.id}>
            <td>
              <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-[var(--radius-sm)] border border-border bg-surface-secondary">
                {item.logo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={item.logo_url}
                    alt=""
                    className="max-h-full max-w-full object-contain p-1"
                  />
                ) : (
                  <span className="font-mono text-[10px] text-muted">
                    {item.name.slice(0, 2).toUpperCase()}
                  </span>
                )}
              </div>
            </td>
            <td>{item.name}</td>
            <td className="text-secondary">{item.slug}</td>
            <td className="text-secondary">
              {item.category_ids?.length
                ? `${item.category_ids.length}`
                : "—"}
            </td>
            <td>{item.is_active ? "Activa" : "Inactiva"}</td>
            <td>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => openEdit(item)}
                >
                  <Pencil className="h-3 w-3" aria-hidden />
                  Editar
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => void toggleActive(item)}
                >
                  {item.is_active ? "Desactivar" : "Activar"}
                </button>
              </div>
            </td>
          </tr>
        ))}
      </AdminTable>

      <FormModal
        open={modalOpen}
        onClose={closeModal}
        title={editing ? "Editar marca" : "Nueva marca"}
        subtitle={editing ? editing.slug : "Se generará el slug al guardar"}
        footer={
          <FormModalActions
            formId={BRAND_FORM_ID}
            submitLabel={editing ? "Guardar cambios" : "Crear marca"}
            saving={saving}
            onCancel={closeModal}
          />
        }
      >
        <BrandForm
          key={editing?.id ?? "new"}
          brand={editing}
          onSavingChange={setSaving}
          onSuccess={() => {
            closeModal();
            void load();
          }}
        />
      </FormModal>
    </AdminShell>
  );
}
