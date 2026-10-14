"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { SiteHeader } from "@/components/SiteHeader";
import { ApiError } from "@/lib/auth-api";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({
    email: "",
    password: "",
    first_name: "",
    last_name: "",
    phone: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (form.password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres");
      return;
    }

    setSubmitting(true);
    try {
      await register({
        email: form.email,
        password: form.password,
        first_name: form.first_name,
        last_name: form.last_name,
        phone: form.phone || undefined,
      });
      router.push("/account");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No se pudo crear la cuenta");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="gema-bg-auth flex min-h-full flex-col text-foreground">
      <SiteHeader>
        <Link href="/login" className="btn-ghost">
          Iniciar sesión
        </Link>
      </SiteHeader>
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <h1 className="font-display mb-2 text-2xl font-semibold text-foreground">
          Crear cuenta
        </h1>
        <p className="mb-8 text-sm text-secondary">
          Regístrate como cliente de GEMA Technology.
        </p>
        <form onSubmit={onSubmit} className="gema-panel space-y-4 p-6 sm:p-8" noValidate>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="first_name" className="label-field">
                Nombre
              </label>
              <input
                id="first_name"
                required
                value={form.first_name}
                onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                className="input-field"
              />
            </div>
            <div>
              <label htmlFor="last_name" className="label-field">
                Apellido
              </label>
              <input
                id="last_name"
                required
                value={form.last_name}
                onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                className="input-field"
              />
            </div>
          </div>
          <div>
            <label htmlFor="email" className="label-field">
              Correo
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="input-field"
              placeholder="tu@email.com"
            />
          </div>
          <div>
            <label htmlFor="phone" className="label-field">
              Teléfono
            </label>
            <input
              id="phone"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="input-field"
              placeholder="0999999999"
            />
          </div>
          <div>
            <label htmlFor="password" className="label-field">
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              className="input-field"
              placeholder="Mínimo 8 caracteres"
            />
          </div>
          {error ? (
            <p className="text-sm font-medium text-error" role="alert">
              {error}
            </p>
          ) : null}
          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? "Creando..." : "Registrarse"}
          </button>
        </form>
      </main>
    </div>
  );
}
