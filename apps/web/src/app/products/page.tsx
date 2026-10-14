import { Suspense } from "react";

import { StoreShell } from "@/components/layout/StoreShell";
import { ProductFilters } from "@/components/products/ProductFilters";
import { ProductInfiniteGrid } from "@/components/products/ProductInfiniteGrid";
import { ProductSortSelect } from "@/components/products/ProductSort";
import { EmptyState } from "@/components/shared/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import {
  loadBrands,
  loadCategories,
  loadProducts,
} from "@/lib/catalog-loader";
import type { ProductSort } from "@/lib/catalog-types";

export const dynamic = "force-dynamic";

const PAGE_SIZE = 12;

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

function first(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) return value[0];
  return value;
}

function parseSort(value: string | undefined): ProductSort {
  const allowed: ProductSort[] = [
    "relevance",
    "price_asc",
    "price_desc",
    "name_asc",
    "name_desc",
    "newest",
  ];
  if (value && (allowed as string[]).includes(value)) {
    return value as ProductSort;
  }
  return "newest";
}

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const sp = await searchParams;
  const category = first(sp.category);
  const brand = first(sp.brand);
  const search = first(sp.search);
  const minPrice = first(sp.min_price);
  const maxPrice = first(sp.max_price);
  const sort = parseSort(first(sp.sort));
  const pageSize = PAGE_SIZE;

  const listQuery = {
    category,
    brand,
    search,
    min_price: minPrice,
    max_price: maxPrice,
    sort,
  };

  const [categoriesResult, brandsResult, productsResult] = await Promise.all([
    loadCategories(),
    loadBrands(category ? { category } : undefined),
    loadProducts({
      ...listQuery,
      page: 1,
      page_size: pageSize,
    }),
  ]);

  const categories = categoriesResult.data ?? [];
  const brands = brandsResult.data ?? [];
  const products = productsResult.data;
  const error =
    productsResult.error || categoriesResult.error || brandsResult.error;

  const hasFilters = Boolean(
    category || brand || search || minPrice || maxPrice,
  );

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-12 sm:py-16">
        <header className="max-w-2xl">
          <h1 className="font-display text-4xl font-semibold tracking-tight text-navy sm:text-5xl">
            Catálogo
          </h1>
          <p className="mt-3 text-base text-secondary sm:text-lg">
            Tecnología seleccionada. Filtra con precisión y encuentra tu
            próximo equipo.
          </p>
        </header>

        <div className="mt-12 grid gap-8 lg:grid-cols-[17.5rem_1fr] lg:gap-12">
          <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start">
            <details className="gema-panel group open:shadow-sm lg:hidden">
              <summary className="cursor-pointer list-none touch-manipulation px-5 py-4 text-sm font-semibold text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
                <span className="flex items-center justify-between gap-2">
                  Filtros
                  <span className="text-xs font-normal text-muted group-open:hidden">
                    Mostrar
                  </span>
                  <span className="hidden text-xs font-normal text-muted group-open:inline">
                    Ocultar
                  </span>
                </span>
              </summary>
              <div className="border-t border-border">
                <Suspense
                  fallback={
                    <div className="space-y-3 p-4">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-9 w-full" />
                      <Skeleton className="h-4 w-20" />
                      <Skeleton className="h-9 w-full" />
                      <Skeleton className="h-9 w-full" />
                    </div>
                  }
                >
                  <ProductFilters
                    categories={categories}
                    brands={brands}
                    embedded
                    idPrefix="m-"
                  />
                </Suspense>
              </div>
            </details>
            <div className="hidden lg:block">
              <Suspense
                fallback={
                  <div className="space-y-4 rounded-[var(--radius-xl)] border border-border bg-surface p-5">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-4 w-20" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                    <Skeleton className="h-9 w-full" />
                  </div>
                }
              >
                <ProductFilters
                  categories={categories}
                  brands={brands}
                  idPrefix="d-"
                />
              </Suspense>
            </div>
          </aside>

          <div className="min-w-0">
            <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <p className="font-mono text-sm text-secondary">
                {products
                  ? `${products.total} resultado${products.total === 1 ? "" : "s"}`
                  : null}
              </p>
              <Suspense fallback={null}>
                <ProductSortSelect />
              </Suspense>
            </div>

            {error ? (
              <div className="gema-panel px-4 py-6 text-sm text-secondary">
                {error.message}
              </div>
            ) : null}

            {!error && products && products.items.length === 0 ? (
              <EmptyState
                title="No encontramos productos con esos filtros."
                description={
                  hasFilters
                    ? "Prueba ampliando el rango de precio o quitando algún filtro."
                    : "Aún no hay productos publicados."
                }
                actionHref="/products"
                actionLabel={hasFilters ? "Limpiar filtros" : "Ir al inicio"}
              />
            ) : null}

            {!error && products && products.items.length > 0 ? (
              <ProductInfiniteGrid
                key={[
                  category ?? "",
                  brand ?? "",
                  search ?? "",
                  minPrice ?? "",
                  maxPrice ?? "",
                  sort,
                ].join("|")}
                initial={{
                  items: products.items,
                  page: products.page,
                  total_pages: products.total_pages,
                  total: products.total,
                }}
                query={listQuery}
                pageSize={pageSize}
              />
            ) : null}
          </div>
        </div>
      </main>
    </StoreShell>
  );
}
