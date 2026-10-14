"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const DEFAULT_PAGE_SIZE = 20;

export type AdminListParams = {
  page: number;
  pageSize: number;
  q: string;
  get: (key: string) => string;
  /** Apply filter values; resets page to 1. Empty string removes the key. */
  applyFilters: (values: Record<string, string>) => void;
  clearFilters: (keys: string[]) => void;
};

function parsePositiveInt(raw: string | null, fallback: number): number {
  if (!raw) return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n >= 1 ? n : fallback;
}

/**
 * URL-driven list state for admin tables (page, page_size, q, + arbitrary filters).
 */
export function useAdminListParams(
  defaults?: { pageSize?: number },
): AdminListParams {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const defaultPageSize = defaults?.pageSize ?? DEFAULT_PAGE_SIZE;

  const page = parsePositiveInt(searchParams.get("page"), 1);
  const pageSize = parsePositiveInt(
    searchParams.get("page_size"),
    defaultPageSize,
  );
  const q = searchParams.get("q")?.trim() ?? "";

  const get = useCallback(
    (key: string) => searchParams.get(key)?.trim() ?? "",
    [searchParams],
  );

  const replaceParams = useCallback(
    (mutate: (next: URLSearchParams) => void) => {
      const next = new URLSearchParams(searchParams.toString());
      mutate(next);
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname);
    },
    [pathname, router, searchParams],
  );

  const applyFilters = useCallback(
    (values: Record<string, string>) => {
      replaceParams((next) => {
        next.delete("page");
        for (const [key, value] of Object.entries(values)) {
          const trimmed = value.trim();
          if (!trimmed) next.delete(key);
          else next.set(key, trimmed);
        }
      });
    },
    [replaceParams],
  );

  const clearFilters = useCallback(
    (keys: string[]) => {
      replaceParams((next) => {
        next.delete("page");
        for (const key of keys) next.delete(key);
      });
    },
    [replaceParams],
  );

  return useMemo(
    () => ({
      page,
      pageSize,
      q,
      get,
      applyFilters,
      clearFilters,
    }),
    [page, pageSize, q, get, applyFilters, clearFilters],
  );
}
