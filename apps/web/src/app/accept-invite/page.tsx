"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { BrandMark } from "@/components/brand/BrandMark";
import { SiteHeader } from "@/components/SiteHeader";
import { adminEmployeesApi } from "@/lib/admin-employees-api";
import { ApiError } from "@/lib/auth-api";

function AcceptInviteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("Falta el token de invitación.");
      return;
    }
    if (password !== confirm) {
      setError("Las contraseñas no coinciden.");
      return;
    }
    setSubmitting(true);
    try {
      await adminEmployeesApi.acceptInvite(token, password);
      router.replace("/login?next=/admin");
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo aceptar la invitación",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={(e) => void onSubmit(e)} className="space-y-4">
      {!token ? (
        <p className="text-sm text-error" role="alert">
          Enlace inválido: falta el token.
        </p>
      ) : null}
      <label className="block text-sm">
        <span className="mb-1 block text-secondary">Nueva contraseña</span>
        <input
          className="w-full border border-border bg-surface px-3 py-2 text-sm"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </label>
      <label className="block text-sm">
        <span className="mb-1 block text-secondary">Confirmar contraseña</span>
        <input
          className="w-full border border-border bg-surface px-3 py-2 text-sm"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
      </label>
      {error ? (
        <p className="text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}
      <button type="submit" className="btn-primary w-full" disabled={submitting || !token}>
        {submitting ? "Activando…" : "Activar cuenta"}
      </button>
    </form>
  );
}

export default function AcceptInvitePage() {
  return (
    <div className="gema-bg-auth flex min-h-full flex-col text-foreground">
      <SiteHeader>
        <Link href="/login" className="btn-ghost">
          Iniciar sesión
        </Link>
      </SiteHeader>
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <div className="mb-8 text-center">
          <BrandMark href={null} className="justify-center" />
          <h1 className="font-display mt-6 text-3xl font-bold tracking-tight text-navy">
            Unirse al equipo
          </h1>
          <p className="mt-2 text-sm text-secondary">
            Define tu contraseña para activar el acceso al panel.
          </p>
        </div>
        <Suspense fallback={<p className="text-sm text-secondary">Cargando…</p>}>
          <AcceptInviteForm />
        </Suspense>
      </main>
    </div>
  );
}
