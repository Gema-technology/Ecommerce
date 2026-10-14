"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ProductCard } from "@/components/products/ProductCard";
import { Stagger } from "@/components/motion/Stagger";
import {
  catalogApi,
  type Product,
  type ProductQuery,
} from "@/lib/catalog-api";
import { useInView } from "@/lib/use-in-view";

type InitialPage = {
  items: Product[];
  page: number;
  total_pages: number;
  total: number;
};

type ListFilters = Omit<ProductQuery, "page" | "page_size">;

export function ProductInfiniteGrid({
  initial,
  query,
  pageSize,
}: {
  initial: InitialPage;
  query: ListFilters;
  pageSize: number;
}) {
  const [items, setItems] = useState(initial.items);
  const [page, setPage] = useState(initial.page);
  const [totalPages, setTotalPages] = useState(initial.total_pages);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadingRef = useRef(false);
  const queryRef = useRef(query);
  queryRef.current = query;

  const hasMore = page < totalPages;
  const { ref: sentinelRef, inView } = useInView<HTMLDivElement>({
    once: false,
    rootMargin: "480px 0px",
    threshold: 0,
  });

  useEffect(() => {
    setItems(initial.items);
    setPage(initial.page);
    setTotalPages(initial.total_pages);
    setError(null);
    loadingRef.current = false;
    setLoading(false);
  }, [initial]);

  const loadNext = useCallback(async () => {
    if (loadingRef.current) return false;
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    try {
      const nextPage = page + 1;
      const data = await catalogApi.listProducts({
        ...queryRef.current,
        page: nextPage,
        page_size: pageSize,
      });
      setItems((prev) => {
        const seen = new Set(prev.map((p) => p.id));
        return [
          ...prev,
          ...data.items.filter((product) => !seen.has(product.id)),
        ];
      });
      setPage(data.page);
      setTotalPages(data.total_pages);
      return true;
    } catch {
      setError("No se pudieron cargar más productos. Intenta de nuevo.");
      return false;
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    if (!inView || !hasMore || loadingRef.current || error) return;
    void loadNext();
  }, [inView, hasMore, error, loadNext]);

  return (
    <div>
      <Stagger className="grid gap-6 sm:grid-cols-2 sm:gap-7 lg:grid-cols-3 lg:gap-8">
        {items.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </Stagger>

      <div
        ref={sentinelRef}
        className="mt-10 flex min-h-12 flex-col items-center justify-center gap-3"
        aria-live="polite"
      >
        {loading ? (
          <p className="font-mono text-xs text-muted">Cargando más…</p>
        ) : null}

        {error ? (
          <div className="flex flex-col items-center gap-2">
            <p className="text-sm text-secondary">{error}</p>
            <button type="button" className="btn-ghost btn-sm" onClick={() => void loadNext()}>
              Reintentar
            </button>
          </div>
        ) : null}

        {!loading && !error && !hasMore && items.length > 0 ? (
          <p className="font-mono text-xs text-muted">
            {initial.total} producto{initial.total === 1 ? "" : "s"} · fin del catálogo
          </p>
        ) : null}

        {!loading && !error && hasMore ? (
          <p className="font-mono text-xs text-muted">Desplázate para ver más</p>
        ) : null}
      </div>
    </div>
  );
}
