"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { adminCustomersApi, type Customer } from "@/lib/admin-customers-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

export default function AdminCustomersPage() {
  const router = useRouter();
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const list = useAdminListParams();
  const active = list.get("active");

  const [items, setItems] = useState<Customer[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
      const data = await adminCustomersApi.list({
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
      setItems([]);
      setTotal(0);
      setTotalPages(0);
      if (err instanceof ApiError && err.status === 401) {
        setError(
          "Sesión expirada o no iniciada. Inicia sesión como administrador.",
        );
        router.replace("/login?next=/admin/customers");
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError("Necesitas rol ADMIN para ver clientes.");
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "No se pudieron cargar clientes",
      );
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, active, router]);

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

  async function toggleCod(customer: Customer) {
    setBusyId(customer.id);
    setError(null);
    try {
      const updated = await adminCustomersApi.setCashOnDelivery(
        customer.id,
        !customer.allow_cash_on_delivery,
      );
      setItems((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      toast.success(
        updated.allow_cash_on_delivery
          ? "Contra entrega habilitado."
          : "Contra entrega deshabilitado.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo actualizar contra entrega";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleActive(customer: Customer) {
    const activating = !customer.is_active;
    if (!activating) {
      const ok = await confirm({
        title: "Desactivar cliente",
        description: `¿Desactivar a ${customer.email}? No podrá iniciar sesión.`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setBusyId(customer.id);
    setError(null);
    try {
      const updated = await adminCustomersApi.setActive(
        customer.id,
        !customer.is_active,
      );
      setItems((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      toast.success(activating ? "Cliente activado." : "Cliente desactivado.");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo actualizar el estado";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <AdminShell title="Clientes">
      {confirmDialog}
      <p className="mb-4 max-w-2xl text-sm text-secondary">
        Compradores de la tienda. Activa{" "}
        <strong className="font-medium text-foreground">Contra entrega</strong>{" "}
        solo para clientes de confianza. El equipo se gestiona en Equipo.
      </p>

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftActive("");
          list.clearFilters(["q", "active"]);
        }}
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Nombre o correo"
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

      {error && (error.includes("sesión") || error.includes("ADMIN")) ? (
        <div className="mb-4 space-y-2">
          <p className="text-sm text-error" role="alert">
            {error}
          </p>
          <Link
            href="/login?next=/admin/customers"
            className="btn-primary inline-flex"
          >
            Ir a iniciar sesión
          </Link>
        </div>
      ) : null}

      <AdminTable
        columns={4}
        loading={loading}
        error={
          error && !(error.includes("sesión") || error.includes("ADMIN"))
            ? error
            : null
        }
        isEmpty={!items.length}
        emptyMessage="Sin clientes."
        meta={`${total} cliente${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>Nombre</th>
            <th>Correo</th>
            <th>Estado</th>
            <th>Contra entrega</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/customers"
          />
        }
      >
        {items.map((u) => (
          <tr key={u.id}>
            <td>
              {u.first_name} {u.last_name}
            </td>
            <td className="font-mono text-xs">{u.email}</td>
            <td>
              <button
                type="button"
                className={u.is_active ? "btn-ghost" : "btn-primary"}
                disabled={busyId === u.id}
                onClick={() => void toggleActive(u)}
              >
                {busyId === u.id ? "…" : u.is_active ? "Activo" : "Inactivo"}
              </button>
            </td>
            <td>
              <button
                type="button"
                className={
                  u.allow_cash_on_delivery ? "btn-primary" : "btn-ghost"
                }
                disabled={busyId === u.id}
                onClick={() => void toggleCod(u)}
              >
                {busyId === u.id
                  ? "…"
                  : u.allow_cash_on_delivery
                    ? "Habilitado"
                    : "Deshabilitado"}
              </button>
            </td>
          </tr>
        ))}
      </AdminTable>
    </AdminShell>
  );
}
