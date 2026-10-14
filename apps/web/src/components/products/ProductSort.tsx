"use client";

import { useRouter, useSearchParams } from "next/navigation";

import type { ProductSort } from "@/lib/catalog-api";
import { cn } from "@/lib/cn";

const OPTIONS: { value: ProductSort; label: string }[] = [
  { value: "newest", label: "Recientes" },
  { value: "relevance", label: "Relevancia" },
  { value: "price_asc", label: "Precio ↑" },
  { value: "price_desc", label: "Precio ↓" },
  { value: "name_asc", label: "A–Z" },
  { value: "name_desc", label: "Z–A" },
];

export function ProductSortSelect({
  basePath = "/products",
}: {
  basePath?: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const current = (params.get("sort") as ProductSort | null) ?? "newest";

  function onSelect(value: ProductSort) {
    const next = new URLSearchParams(params.toString());
    if (value && value !== "newest") next.set("sort", value);
    else next.delete("sort");
    next.delete("page");
    router.push(next.toString() ? `${basePath}?${next}` : basePath);
  }

  return (
    <div
      className="flex w-full min-w-0 flex-col gap-2 sm:w-auto"
      role="group"
      aria-label="Ordenar productos"
    >
      <span className="label-field mb-0 font-mono text-[0.625rem] uppercase tracking-[0.1em]">
        Sort
      </span>
      <div className="flex flex-wrap gap-1.5">
        {OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            className={cn(
              "gema-filter-chip",
              current === opt.value && "is-active",
            )}
            aria-pressed={current === opt.value}
            onClick={() => onSelect(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
