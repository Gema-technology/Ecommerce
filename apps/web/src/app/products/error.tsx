"use client";

import Link from "next/link";
import { useEffect } from "react";

import { StoreShell } from "@/components/layout/StoreShell";

export default function ProductsError({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Avoid exposing stack traces in the UI.
  }, []);

  return (
    <StoreShell>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-16 sm:px-6">
        <h1 className="text-2xl font-semibold">Algo salió mal</h1>
        <p className="mt-2 text-sm text-secondary">
          No pudimos cargar el catálogo. Intenta de nuevo.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <button type="button" className="btn-primary" onClick={reset}>
            Reintentar
          </button>
          <Link href="/" className="btn-ghost">
            Ir al inicio
          </Link>
        </div>
      </main>
    </StoreShell>
  );
}
