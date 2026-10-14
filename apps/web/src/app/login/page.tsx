"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { BrandMark } from "@/components/brand/BrandMark";
import { useAuth } from "@/components/auth/AuthProvider";
import { SiteHeader } from "@/components/SiteHeader";
import { Button, FormField, Input } from "@/components/ui";
import { ApiError } from "@/lib/auth-api";

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("No se pudo iniciar sesión");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="gema-bg-auth flex min-h-full flex-col text-foreground">
      <SiteHeader>
        <Link href="/register" className="btn-ghost">
          Crear cuenta
        </Link>
      </SiteHeader>
      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
        <div className="mb-8 text-center">
          <BrandMark href={null} className="justify-center" />
          <h1 className="font-display mt-6 text-3xl font-bold tracking-tight text-navy">
            Iniciar sesión
          </h1>
          <p className="mt-2 text-sm text-secondary">
            Accede a tu cuenta de GEMA Technology.
          </p>
        </div>
        <form
          onSubmit={onSubmit}
          className="gema-panel-elevated form-stack p-6 sm:p-8"
          noValidate
        >
          <FormField label="Correo">
            <Input
              id="email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="tu@email.com"
            />
          </FormField>
          <FormField label="Contraseña" hint="Mínimo 8 caracteres">
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </FormField>
          {error ? (
            <p className="field-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="form-actions">
            <Button type="submit" loading={submitting} className="w-full">
              Entrar
            </Button>
          </div>
        </form>
        <p className="mt-6 text-center text-sm text-secondary">
          ¿No tienes cuenta?{" "}
          <Link href="/register" className="text-primary hover:underline">
            Crear cuenta
          </Link>
        </p>
      </main>
    </div>
  );
}
