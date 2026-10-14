import Link from "next/link";

import { StoreShell } from "@/components/layout/StoreShell";
import { loadBrands } from "@/lib/catalog-loader";

export const dynamic = "force-dynamic";

export default async function BrandsPage() {
  const result = await loadBrands();
  const brands = result.data ?? [];

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-12 sm:py-16">
        <header className="max-w-2xl">
          <h1 className="font-display text-4xl font-semibold tracking-tight text-navy sm:text-5xl">
            Marcas
          </h1>
          <p className="mt-3 text-base text-secondary sm:text-lg">
            Selección de fabricantes con los que trabajamos. Entra a ver su
            catálogo completo.
          </p>
        </header>

        {result.error ? (
          <p className="gema-panel mt-10 border-warning/30 px-4 py-3 text-sm text-warning">
            {result.error.message}
          </p>
        ) : null}

        {!result.error && brands.length === 0 ? (
          <p className="mt-10 text-sm text-muted">No hay marcas activas.</p>
        ) : null}

        {brands.length > 0 ? (
          <ul className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {brands.map((brand) => (
              <li key={brand.id}>
                <Link
                  href={`/products?brand=${brand.slug}`}
                  className="gema-card gema-card-interactive group flex items-center gap-5 p-6 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                >
                  <div className="gema-card-media flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden">
                    {brand.logo_url ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={brand.logo_url}
                        alt=""
                        className="h-full w-full object-contain p-2"
                      />
                    ) : (
                      <span className="font-mono text-sm font-medium text-navy/30">
                        {brand.name.slice(0, 2).toUpperCase()}
                      </span>
                    )}
                  </div>
                  <div className="min-w-0">
                    <p className="gema-card-label mb-1">Marca</p>
                    <h2 className="font-display text-lg font-semibold tracking-tight text-navy transition duration-150 group-hover:text-primary">
                      {brand.name}
                    </h2>
                    {brand.description ? (
                      <p className="mt-1 line-clamp-2 text-sm text-secondary">
                        {brand.description}
                      </p>
                    ) : (
                      <p className="mt-1 font-mono text-xs text-muted">VER →</p>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </main>
    </StoreShell>
  );
}
