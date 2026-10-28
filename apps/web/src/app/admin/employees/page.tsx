"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import {
  adminEmployeesApi,
  inviteUrlOnCurrentSite,
  type Employee,
  type StaffRole,
} from "@/lib/admin-employees-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

export default function AdminEmployeesPage() {
  const router = useRouter();
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const { user } = useAuth();
  const isSuperAdmin = Boolean(user?.roles.includes("SUPER_ADMIN"));
  const list = useAdminListParams();
  const status = list.get("status");

  const [items, setItems] = useState<Employee[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [copying, setCopying] = useState(false);

  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [role, setRole] = useState<StaffRole>("ADMIN");

  const [draftQ, setDraftQ] = useState(list.q);
  const [draftStatus, setDraftStatus] = useState(status);

  useEffect(() => {
    setDraftQ(list.q);
    setDraftStatus(status);
  }, [list.q, status]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await adminEmployeesApi.list({
        page: list.page,
        page_size: list.pageSize,
        q: list.q || undefined,
        status: status || undefined,
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
        router.replace("/login?next=/admin/employees");
        return;
      }
      if (err instanceof ApiError && err.status === 403) {
        setError("Necesitas rol ADMIN para ver el equipo.");
        return;
      }
      setError(
        err instanceof ApiError ? err.message : "No se pudo cargar el equipo",
      );
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, status, router]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      q: draftQ,
      status: draftStatus,
    });
  }

  async function copyInviteUrl() {
    if (!inviteUrl) return;
    setCopying(true);
    try {
      await navigator.clipboard.writeText(inviteUrl);
      toast.success("Enlace copiado al portapapeles.");
    } catch {
      toast.error("No se pudo copiar el enlace.");
    } finally {
      setCopying(false);
    }
  }

  async function onInvite(event: FormEvent) {
    event.preventDefault();
    if (!isSuperAdmin) return;
    setSubmitting(true);
    setError(null);
    setInviteUrl(null);
    try {
      const created = await adminEmployeesApi.invite({
        email,
        first_name: firstName,
        last_name: lastName,
        role,
        job_title: jobTitle || null,
      });
      setInviteUrl(inviteUrlOnCurrentSite(created.invite_url));
      setEmail("");
      setFirstName("");
      setLastName("");
      setJobTitle("");
      setRole("ADMIN");
      await load();
      toast.success(
        created.email_sent
          ? "Invitación enviada por correo. El enlace también está aquí."
          : "Invitación lista. El correo no está activo: copia el enlace y envíalo.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo enviar la invitación";
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  async function changeRole(employee: Employee, next: StaffRole) {
    setBusyId(employee.id);
    setError(null);
    try {
      const updated = await adminEmployeesApi.setRole(employee.id, next);
      setItems((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
      toast.success("Rol actualizado.");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo cambiar el rol";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleActive(employee: Employee) {
    const activating = !employee.is_active;
    if (!activating) {
      const ok = await confirm({
        title: "Desactivar empleado",
        description: `¿Desactivar a ${employee.email}? No podrá iniciar sesión.`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setBusyId(employee.id);
    setError(null);
    try {
      const updated = await adminEmployeesApi.setActive(
        employee.id,
        !employee.is_active,
      );
      setItems((prev) => prev.map((e) => (e.id === updated.id ? updated : e)));
      toast.success(activating ? "Empleado activado." : "Empleado desactivado.");
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

  async function resendInvite(employee: Employee) {
    setBusyId(employee.id);
    setError(null);
    setInviteUrl(null);
    try {
      const result = await adminEmployeesApi.resendInvite(employee.id);
      setInviteUrl(inviteUrlOnCurrentSite(result.invite_url));
      await load();
      toast.success(
        result.email_sent
          ? "Invitación reenviada por correo."
          : "Nuevo enlace listo. Cópialo y envíalo: el correo no está activo.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo reenviar la invitación";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  async function resetPassword(employee: Employee) {
    const ok = await confirm({
      title: "Resetear contraseña",
      description: `¿Resetear contraseña de ${employee.email}? La clave actual dejará de funcionar y se generará un enlace nuevo (48h).`,
      confirmLabel: "Resetear",
      tone: "danger",
    });
    if (!ok) return;

    setBusyId(employee.id);
    setError(null);
    setInviteUrl(null);
    try {
      const result = await adminEmployeesApi.resetPassword(employee.id);
      setInviteUrl(inviteUrlOnCurrentSite(result.invite_url));
      await load();
      toast.success("Contraseña reseteada. Comparte el nuevo enlace.");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo resetear la contraseña";
      setError(msg);
      toast.error(msg);
    } finally {
      setBusyId(null);
    }
  }

  const columns = isSuperAdmin ? 7 : 6;

  return (
    <AdminShell title="Equipo">
      {confirmDialog}
      <p className="mb-4 max-w-2xl text-sm text-secondary">
        Empleados con acceso al panel. Solo SUPER_ADMIN puede invitar, reenviar
        enlace, resetear contraseña o cambiar roles. Si el correo no está
        activo, la invitación es el enlace que aparece al invitar. El personal
        no se registra por la tienda.
      </p>

      {isSuperAdmin ? (
        <form
          onSubmit={(e) => void onInvite(e)}
          className="gema-panel mb-6 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-3"
        >
          <h2 className="font-display col-span-full text-base font-semibold">
            Invitar empleado
          </h2>
          <label className="block text-sm">
            <span className="mb-1 block text-secondary">Correo</span>
            <input
              className="w-full border border-border bg-surface px-3 py-2 text-sm"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-secondary">Nombre</span>
            <input
              className="w-full border border-border bg-surface px-3 py-2 text-sm"
              required
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-secondary">Apellido</span>
            <input
              className="w-full border border-border bg-surface px-3 py-2 text-sm"
              required
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-secondary">Cargo</span>
            <input
              className="w-full border border-border bg-surface px-3 py-2 text-sm"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-secondary">Rol</span>
            <select
              className="w-full border border-border bg-surface px-3 py-2 text-sm"
              value={role}
              onChange={(e) => setRole(e.target.value as StaffRole)}
            >
              <option value="ADMIN">ADMIN</option>
              <option value="SUPER_ADMIN">SUPER_ADMIN</option>
            </select>
          </label>
          <div className="flex items-end">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Invitando…" : "Invitar"}
            </button>
          </div>
        </form>
      ) : (
        <p className="mb-4 text-sm text-secondary">
          Solo un super administrador puede invitar empleados.
        </p>
      )}

      {inviteUrl ? (
        <div className="gema-panel mb-4 space-y-2 p-4" role="status">
          <p className="text-sm font-medium text-foreground">
            Enlace de invitación (compartir con el empleado)
          </p>
          <p className="text-xs text-secondary">
            Válido 48 horas. Compártelo con el empleado. Sin correo configurado,
            este enlace es la invitación.
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <code className="min-w-0 flex-1 break-all rounded border border-border bg-surface-secondary px-3 py-2 font-mono text-xs">
              {inviteUrl}
            </code>
            <button
              type="button"
              className="btn-secondary btn-sm"
              disabled={copying}
              onClick={() => void copyInviteUrl()}
            >
              {copying ? "Copiando…" : "Copiar enlace"}
            </button>
          </div>
        </div>
      ) : null}

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftStatus("");
          list.clearFilters(["q", "status"]);
        }}
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="Nombre o correo"
          />
        </FormField>
        <FormField label="Estado" className="w-40 min-w-0">
          <Select
            value={draftStatus}
            onChange={(e) => setDraftStatus(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="invited">Invitado</option>
            <option value="active">Activo</option>
            <option value="inactive">Inactivo</option>
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={columns}
        loading={loading}
        error={error}
        isEmpty={!items.length}
        emptyMessage="Sin empleados."
        meta={`${total} empleado${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>Nombre</th>
            <th>Correo</th>
            <th>Cargo</th>
            <th>Estado</th>
            <th>Rol</th>
            <th>Cuenta</th>
            {isSuperAdmin ? <th>Acceso</th> : null}
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/employees"
          />
        }
      >
        {items.map((e) => {
          const staffRole: StaffRole = e.roles.includes("SUPER_ADMIN")
            ? "SUPER_ADMIN"
            : "ADMIN";
          return (
            <tr key={e.id}>
              <td>
                {e.first_name} {e.last_name}
              </td>
              <td className="font-mono text-xs">{e.email}</td>
              <td className="text-sm">{e.job_title || "—"}</td>
              <td className="text-xs uppercase">{e.status}</td>
              <td>
                {isSuperAdmin ? (
                  <select
                    className="border border-border bg-surface px-2 py-1 text-xs"
                    value={staffRole}
                    disabled={busyId === e.id}
                    onChange={(ev) =>
                      void changeRole(e, ev.target.value as StaffRole)
                    }
                  >
                    <option value="ADMIN">ADMIN</option>
                    <option value="SUPER_ADMIN">SUPER_ADMIN</option>
                  </select>
                ) : (
                  <span className="text-xs">{e.roles.join(", ")}</span>
                )}
              </td>
              <td>
                <button
                  type="button"
                  className={e.is_active ? "btn-ghost" : "btn-primary"}
                  disabled={busyId === e.id || e.status === "invited"}
                  onClick={() => void toggleActive(e)}
                >
                  {busyId === e.id
                    ? "…"
                    : e.is_active
                      ? "Activo"
                      : "Inactivo"}
                </button>
              </td>
              {isSuperAdmin ? (
                <td className="space-x-2 whitespace-nowrap">
                  {e.status === "invited" ? (
                    <button
                      type="button"
                      className="btn-ghost text-xs"
                      disabled={busyId === e.id}
                      onClick={() => void resendInvite(e)}
                    >
                      Reenviar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn-ghost text-xs"
                      disabled={busyId === e.id}
                      onClick={() => void resetPassword(e)}
                    >
                      Reset clave
                    </button>
                  )}
                </td>
              ) : null}
            </tr>
          );
        })}
      </AdminTable>
    </AdminShell>
  );
}
