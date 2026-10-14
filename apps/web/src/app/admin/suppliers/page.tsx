"use client";

import { Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import {
  FormModal,
  FormModalActions,
} from "@/components/admin/forms/AdminFormPrimitives";
import { SupplierForm, SUPPLIER_FORM_ID } from "@/components/admin/SupplierForm";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { suppliersApi, type Supplier } from "@/lib/suppliers-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

export default function AdminSuppliersPage() {
  const router = useRouter();
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const list = useAdminListParams();
  const active = list.get("active");

  const [items, setItems] = useState<Supplier[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
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
      const data = await suppliersApi.list({
        page: list.page,
        page_size: list.pageSize,
        search: list.q || undefined,
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

  function openEdit(supplier: Supplier) {
    setEditing(supplier);
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditing(null);
  }

  async function toggleActive(supplier: Supplier) {
    if (supplier.is_active) {
      const ok = await confirm({
        title: "Desactivar proveedor",
        description: `¿Desactivar «${supplier.business_name}»?`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setError(null);
    try {
      if (supplier.is_active) {
        await suppliersApi.remove(supplier.id);
        toast.success("Proveedor desactivado.");
      } else {
        await suppliersApi.update(supplier.id, { is_active: true });
        toast.success("Proveedor activado.");
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
    <AdminShell title="Proveedores">
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
            Nuevo proveedor
          </button>
        }
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Nombre o RUC"
          />
        </FormField>
        <FormField label="Estado" className="w-36 min-w-0">
          <Select
            value={draftActive}
            onChange={(e) => setDraftActive(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={6}
        loading={loading}
        error={error}
        isEmpty={!items.length}
        emptyMessage="No hay proveedores."
        meta={`${total} proveedor${total === 1 ? "" : "es"}`}
        head={
          <tr>
            <th>Razón social</th>
            <th>Comercial</th>
            <th>Tax ID</th>
            <th>Ciudad</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/suppliers"
          />
        }
      >
        {items.map((s) => (
          <tr key={s.id}>
            <td>{s.business_name}</td>
            <td>{s.commercial_name ?? "—"}</td>
            <td className="font-mono text-xs">
              {s.tax_id_type}:{s.tax_id}
            </td>
            <td>{s.city ?? "—"}</td>
            <td>{s.is_active ? "Activo" : "Inactivo"}</td>
            <td>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => openEdit(s)}
                >
                  <Pencil className="h-3 w-3" aria-hidden />
                  Editar
                </button>
                <Link
                  href={`/admin/suppliers/${s.id}`}
                  className="btn-ghost btn-sm"
                >
                  Ver
                </Link>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => void toggleActive(s)}
                >
                  {s.is_active ? "Desactivar" : "Activar"}
                </button>
              </div>
            </td>
          </tr>
        ))}
      </AdminTable>

      <FormModal
        open={modalOpen}
        onClose={closeModal}
        size="lg"
        title={editing ? "Editar proveedor" : "Nuevo proveedor"}
        subtitle={editing ? editing.tax_id : "Datos fiscales y de contacto"}
        footer={
          <FormModalActions
            formId={SUPPLIER_FORM_ID}
            submitLabel={editing ? "Guardar cambios" : "Crear proveedor"}
            saving={saving}
            onCancel={closeModal}
          />
        }
      >
        <SupplierForm
          key={editing?.id ?? "new"}
          supplier={editing}
          onSavingChange={setSaving}
          onSuccess={(saved) => {
            closeModal();
            if (!editing) {
              router.push(`/admin/suppliers/${saved.id}`);
              return;
            }
            void load();
          }}
        />
      </FormModal>
    </AdminShell>
  );
}
