import { Suspense } from "react";
import Link from "next/link";
import { notFound } from "next/navigation";
import type { Metadata } from "next";

import { CategoryTreeList } from "@/components/categories/CategoryTreeList";
import { StoreShell } from "@/components/layout/StoreShell";
import { ProductFilters } from "@/components/products/ProductFilters";
import { ProductGrid } from "@/components/products/ProductGrid";
import { ProductSortSelect } from "@/components/products/ProductSort";
import { EmptyState } from "@/components/shared/EmptyState";
import { Pagination } from "@/components/shared/Pagination";
import { Skeleton } from "@/components/ui/skeleton";
import type { ProductSort } from "@/lib/catalog-types";
import {
  getCategoryAncestors,
  getSubtreeNode,
  loadBrands,
  loadCategories,
  loadCategory,
  loadProducts,
} from "@/lib/catalog-loader";

export const dynamic = "force-dynamic";

type Params = Promise<{ slug: string }>;
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

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { slug } = await params;
  const result = await loadCategory(slug);
  if (!result.data) {
    return { title: "Categoría no encontrada | GEMA Technology" };
  }
  const title = `${result.data.name} | GEMA Technology`;
  return {
    title,
    description:
      result.data.description ||
      `Productos de ${result.data.name} en GEMA Technology`,
    openGraph: { title, description: result.data.description ?? undefined },
  };
}

export default async function CategoryDetailPage({
  params,
  searchParams,
}: {
  params: Params;
  searchParams: SearchParams;
}) {
  const { slug } = await params;
  const sp = await searchParams;

  const categoryResult = await loadCategory(slug);
  if (categoryResult.error?.kind === "not_found") {
    notFound();
  }
  if (categoryResult.error || !categoryResult.data) {
    return (
      <StoreShell>
        <main className="gema-container flex-1 py-16">
          <h1 className="font-display text-2xl font-semibold">
            No pudimos cargar la categoría
          </h1>
          <p className="mt-2 text-sm text-secondary">
            {categoryResult.error?.message}
          </p>
          <Link href="/categories" className="btn-primary mt-6 inline-flex">
            Ver categorías
          </Link>
        </main>
      </StoreShell>
    );
  }

  const category = categoryResult.data;
  const brand = first(sp.brand);
  const search = first(sp.search);
  const minPrice = first(sp.min_price);
  const maxPrice = first(sp.max_price);
  const sort = parseSort(first(sp.sort));
  const page = Math.max(1, Number(first(sp.page) || "1") || 1);
  const pageSize = Math.min(
    48,
    Math.max(1, Number(first(sp.page_size) || "12") || 12),
  );
  const basePath = `/categories/${category.slug}`;

  const [allCategories, brandsResult, productsResult] = await Promise.all([
    loadCategories(),
    loadBrands({ category: category.slug }),
    loadProducts({
      category: category.slug,
      brand,
      search,
      min_price: minPrice,
      max_price: maxPrice,
      sort,
      page,
      page_size: pageSize,
    }),
  ]);

  const categories = allCategories.data ?? [];
  const ancestors = getCategoryAncestors(category, categories);
  const subtree = getSubtreeNode(category.id, categories);
  const childNodes = subtree?.children ?? [];
  const brands = brandsResult.data ?? [];
  const products = productsResult.data;
  const hasFilters = Boolean(brand || search || minPrice || maxPrice);

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-10">
        <nav className="mb-4 text-sm text-secondary" aria-label="Miga de pan">
          <Link href="/categories" className="hover:text-foreground">
            Categorías
          </Link>
          {ancestors.map((ancestor) => (
            <span key={ancestor.id}>
              <span className="mx-2">/</span>
              <Link
                href={`/categories/${ancestor.slug}`}
                className="hover:text-foreground"
              >
                {ancestor.name}
              </Link>
            </span>
          ))}
          <span className="mx-2">/</span>
          <span className="text-foreground">{category.name}</span>
        </nav>

        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
          {category.image_url ? (
            <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-md)] border border-border bg-surface-secondary">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={category.image_url}
                alt=""
                className="max-h-full max-w-full object-contain p-2"
              />
            </div>
          ) : null}
          <div className="min-w-0">
            <h1 className="font-display text-2xl font-semibold">
              {category.name}
            </h1>
            {category.description ? (
              <p className="mt-2 max-w-2xl text-secondary">
                {category.description}
              </p>
            ) : null}
            <p className="mt-2 font-mono text-xs text-muted">
              Incluye productos de esta categoría y de todas sus subcategorías.
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[16rem_1fr] lg:gap-8">
          <aside className="min-w-0 space-y-4 lg:sticky lg:top-24 lg:self-start">
            {childNodes.length ? (
              <div className="gema-panel-elevated p-4">
                <p className="font-display text-sm font-semibold text-navy">
                  Subcategorías
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-muted">
                  ÁRBOL
                </p>
                <div className="mt-3">
                  <CategoryTreeList
                    nodes={childNodes}
                    activeSlug={category.slug}
                    defaultOpenDepth={2}
                  />
                </div>
              </div>
            ) : null}

            <details className="gema-panel group open:shadow-sm lg:hidden">
              <summary className="cursor-pointer list-none px-4 py-3.5 text-sm font-semibold text-foreground marker:content-none [&::-webkit-details-marker]:hidden">
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
                    basePath={basePath}
                    hideCategory
                    lockedCategory={category.slug}
                    embedded
                    idPrefix="cm-"
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
                  basePath={basePath}
                  hideCategory
                  lockedCategory={category.slug}
                  idPrefix="cd-"
                />
              </Suspense>
            </div>
          </aside>
          <div className="min-w-0">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
              <p className="text-sm text-secondary">
                {products
                  ? `${products.total} resultado${products.total === 1 ? "" : "s"}`
                  : null}
              </p>
              <Suspense fallback={null}>
                <ProductSortSelect basePath={basePath} />
              </Suspense>
            </div>

            {productsResult.error ? (
              <div className="gema-panel px-4 py-6 text-sm text-secondary">
                {productsResult.error.message}
              </div>
            ) : null}

            {!productsResult.error && products && products.items.length === 0 ? (
              <EmptyState
                title="No encontramos productos con esos filtros."
                actionHref={basePath}
                actionLabel="Limpiar filtros"
                description={
                  hasFilters
                    ? undefined
                    : "Esta categoría aún no tiene productos publicados."
                }
              />
            ) : null}

            {!productsResult.error && products && products.items.length > 0 ? (
              <>
                <ProductGrid products={products.items} />
                <Suspense fallback={null}>
                  <Pagination
                    page={products.page}
                    totalPages={products.total_pages}
                    basePath={basePath}
                  />
                </Suspense>
              </>
            ) : null}
          </div>
        </div>
      </main>
    </StoreShell>
  );
}
