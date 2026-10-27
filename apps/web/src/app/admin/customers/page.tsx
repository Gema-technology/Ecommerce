"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { adminCustomersApi, type Customer } from "@/lib/admin-customers-api";
import { citiesForProvince, ECUADOR_PROVINCES } from "@/lib/checkout-types";
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
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Customer | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [taxIdType, setTaxIdType] = useState("");
  const [taxId, setTaxId] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [addressReference, setAddressReference] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);

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

  function openCreate() {
    setEditing(null);
    setFirstName("");
    setLastName("");
    setEmail("");
    setPhone("");
    setTaxIdType("");
    setTaxId("");
    setAddressLine("");
    setAddressReference("");
    setProvince("");
    setCity("");
    setPostalCode("");
    setPassword("");
    setFormOpen(true);
  }

  function openEdit(customer: Customer) {
    setEditing(customer);
    setFirstName(customer.first_name);
    setLastName(customer.last_name);
    setEmail(customer.email);
    setPhone(customer.phone ?? "");
    setTaxIdType(customer.tax_id_type ?? "");
    setTaxId(customer.tax_id ?? "");
    setAddressLine(customer.address_line ?? "");
    setAddressReference(customer.address_reference ?? "");
    setProvince(customer.province ?? "");
    setCity(customer.city ?? "");
    setPostalCode(customer.postal_code ?? "");
    setPassword("");
    setFormOpen(true);
  }

  async function saveCustomer(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        const updated = await adminCustomersApi.update(editing.id, {
          email: email.trim(),
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone.trim(),
          tax_id_type: taxIdType as Customer["tax_id_type"],
          tax_id: taxId.trim(),
          address_line: addressLine.trim(),
          address_reference: addressReference.trim() || null,
          city,
          province,
          country: "Ecuador",
          postal_code: postalCode.trim() || null,
          ...(password ? { password } : {}),
        });
        setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
        toast.success("Cliente actualizado.");
      } else {
        await adminCustomersApi.create({
          email: email.trim(),
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          phone: phone.trim(),
          tax_id_type: taxIdType as Customer["tax_id_type"],
          tax_id: taxId.trim(),
          address_line: addressLine.trim(),
          address_reference: addressReference.trim() || null,
          city,
          province,
          country: "Ecuador",
          postal_code: postalCode.trim() || null,
        });
        toast.success("Cliente registrado.");
        await load();
      }
      setFormOpen(false);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "No se pudo guardar el cliente";
      setError(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }

  async function removeCustomer(customer: Customer) {
    const ok = await confirm({
      title: "Eliminar cliente",
      description: `¿Eliminar a ${customer.first_name} ${customer.last_name}? Si tiene pedidos, solo podrás desactivarlo.`,
      confirmLabel: "Eliminar",
      tone: "danger",
    });
    if (!ok) return;
    setBusyId(customer.id);
    setError(null);
    try {
      await adminCustomersApi.remove(customer.id);
      toast.success("Cliente eliminado.");
      await load();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "No se pudo eliminar el cliente";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

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
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-secondary">
          Datos para facturar: identificación, teléfono y dirección. La
          contraseña solo hace falta si la persona va a entrar a la tienda web.
          El equipo se gestiona en Equipo.
        </p>
        <button type="button" className="btn-primary" onClick={openCreate}>
          Nuevo cliente
        </button>
      </div>

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
        columns={6}
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
            <th>Teléfono</th>
            <th>Identificación</th>
            <th>Estado</th>
            <th>Acciones</th>
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
            <td>{u.phone || "—"}</td>
            <td>{u.tax_id ? `${u.tax_id_type === "RUC" ? "RUC" : u.tax_id_type === "PASAPORTE" ? "Pasaporte" : "Cédula"} ${u.tax_id}` : "—"}</td>
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
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => openEdit(u)}
                >
                  Editar
                </button>
                <button
                  type="button"
                  className={u.allow_cash_on_delivery ? "btn-primary btn-sm" : "btn-ghost btn-sm"}
                  disabled={busyId === u.id}
                  onClick={() => void toggleCod(u)}
                >
                  {u.allow_cash_on_delivery ? "Contra entrega" : "Sin contra entrega"}
                </button>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  disabled={busyId === u.id}
                  onClick={() => void removeCustomer(u)}
                >
                  Eliminar
                </button>
              </div>
            </td>
          </tr>
        ))}
      </AdminTable>

      <Modal
        open={formOpen}
        title={editing ? "Editar cliente" : "Nuevo cliente"}
        onClose={() => setFormOpen(false)}
      >
        <form onSubmit={(event) => void saveCustomer(event)} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Nombre" required>
              <Input
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                required
              />
            </FormField>
            <FormField label="Apellido" required>
              <Input
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                required
              />
            </FormField>
            <FormField label="Correo" required>
              <Input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </FormField>
            <FormField label="Teléfono" required>
              <Input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
              />
            </FormField>
            <FormField label="Identificación" required>
              <Select
                value={taxIdType}
                onChange={(event) => setTaxIdType(event.target.value)}
                required
              >
                <option value="">Seleccionar…</option>
                <option value="CEDULA">Cédula</option>
                <option value="RUC">RUC</option>
                <option value="PASAPORTE">Pasaporte</option>
              </Select>
            </FormField>
            <FormField label="Número" required>
              <Input
                value={taxId}
                onChange={(event) => setTaxId(event.target.value)}
                inputMode={taxIdType === "PASAPORTE" ? "text" : "numeric"}
                required
              />
            </FormField>
            <FormField label="Provincia" required>
              <Select
                value={province}
                required
                onChange={(event) => {
                  setProvince(event.target.value);
                  setCity("");
                }}
              >
                <option value="">Seleccionar…</option>
                {ECUADOR_PROVINCES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Ciudad" required>
              <Select
                value={city}
                required
                disabled={!province}
                onChange={(event) => setCity(event.target.value)}
              >
                <option value="">
                  {province ? "Seleccionar…" : "Elige provincia primero"}
                </option>
                {citiesForProvince(province).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Dirección" required className="sm:col-span-2">
              <Input
                value={addressLine}
                onChange={(event) => setAddressLine(event.target.value)}
                required
              />
            </FormField>
            <FormField label="Referencia">
              <Input
                value={addressReference}
                onChange={(event) => setAddressReference(event.target.value)}
                placeholder="Opcional"
              />
            </FormField>
            <FormField label="Código postal">
              <Input
                value={postalCode}
                onChange={(event) => setPostalCode(event.target.value)}
                placeholder="Opcional"
              />
            </FormField>
            {editing ? (
              <FormField
                label="Nueva contraseña"
                hint="Opcional. Déjala vacía para no cambiar el acceso."
                className="sm:col-span-2"
              >
                <Input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={8}
                  autoComplete="new-password"
                />
              </FormField>
            ) : null}
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-ghost" onClick={() => setFormOpen(false)}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Guardando…" : "Guardar"}
            </button>
          </div>
        </form>
      </Modal>
    </AdminShell>
  );
}
