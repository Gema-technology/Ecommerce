"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { RequireAuth } from "@/components/auth/RequireAuth";
import { useAuth } from "@/components/auth/AuthProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { Button, FormField, Input } from "@/components/ui";
import { ApiError, authApi, type User } from "@/lib/auth-api";

function AccountForm({ user }: { user: User }) {
  const { refresh, logout } = useAuth();
  const router = useRouter();
  const [firstName, setFirstName] = useState(user.first_name);
  const [lastName, setLastName] = useState(user.last_name);
  const [phone, setPhone] = useState(user.phone ?? "");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await authApi.updateProfile({
        first_name: firstName,
        last_name: lastName,
        phone: phone || null,
      });
      await refresh();
      setMessage("Perfil actualizado");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No se pudo actualizar el perfil");
      }
    } finally {
      setSaving(false);
    }
  }

  async function onLogout() {
    await logout();
    router.push("/");
  }

  return (
    <StoreShell>
      <main className="gema-container max-w-lg flex-1 py-12">
        <h1 className="font-display mb-2 text-2xl font-semibold text-navy">
          Mi cuenta
        </h1>
        <p className="mb-2 text-sm text-secondary">{user.email}</p>
        <p className="mb-6 text-sm text-secondary">
          Permisos:{" "}
          <span className="font-medium text-foreground">
            {user.roles.join(", ")}
          </span>
        </p>

        <div className="mb-8 flex flex-wrap gap-2">
          <Link href="/products" className="btn-primary">
            Ver productos
          </Link>
          <Link href="/orders" className="btn-ghost">
            Mis órdenes
          </Link>
          <Link href="/categories" className="btn-ghost">
            Categorías
          </Link>
          {user.roles.includes("ADMIN") ||
          user.roles.includes("SUPER_ADMIN") ? (
            <Link href="/admin" className="btn-ghost">
              Panel de administración
            </Link>
          ) : null}
        </div>

        <form onSubmit={onSave} className="gema-panel-elevated form-stack p-6">
          <FormField label="Nombre">
            <Input
              id="first_name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
            />
          </FormField>
          <FormField label="Apellido">
            <Input
              id="last_name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
            />
          </FormField>
          <FormField label="Teléfono" hint="Opcional">
            <Input
              id="phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </FormField>
          {message ? (
            <p className="text-sm font-medium text-success">{message}</p>
          ) : null}
          {error ? (
            <p className="field-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="form-actions">
            <Button type="submit" loading={saving}>
              Guardar cambios
            </Button>
          </div>
        </form>

        <Button
          type="button"
          variant="ghost"
          className="mt-6"
          onClick={() => void onLogout()}
        >
          Cerrar sesión
        </Button>
      </main>
    </StoreShell>
  );
}

function AccountContent() {
  const { user } = useAuth();
  if (!user) return null;
  return <AccountForm key={user.id} user={user} />;
}

export default function AccountPage() {
  return (
    <RequireAuth>
      <AccountContent />
    </RequireAuth>
  );
}
