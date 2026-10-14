"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { CategoryPicker } from "@/components/categories/CategoryPicker";
import { Select } from "@/components/ui/select";
import { catalogApi, type Brand, type Category, type ProductSort } from "@/lib/catalog-api";

export function ProductFilters({
  categories,
  brands: initialBrands,
  basePath = "/products",
  hideCategory = false,
  lockedCategory,
  embedded = false,
  idPrefix = "",
}: {
  categories: Category[];
  brands: Brand[];
  basePath?: string;
  hideCategory?: boolean;
  lockedCategory?: string;
  embedded?: boolean;
  idPrefix?: string;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const [category, setCategory] = useState(
    lockedCategory ?? params.get("category") ?? "",
  );
  const [brand, setBrand] = useState(params.get("brand") ?? "");
  const [brands, setBrands] = useState<Brand[]>(initialBrands);
  const [minPrice, setMinPrice] = useState(params.get("min_price") ?? "");
  const [maxPrice, setMaxPrice] = useState(params.get("max_price") ?? "");
  const [search, setSearch] = useState(params.get("search") ?? "");

  const sort = (params.get("sort") as ProductSort | null) ?? "newest";
  const sid = (name: string) => `${idPrefix}${name}`;
  const effectiveCategory = lockedCategory ?? category;

  useEffect(() => {
    setBrands(initialBrands);
  }, [initialBrands]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await catalogApi.listBrands(
          false,
          effectiveCategory ? { category: effectiveCategory } : undefined,
        );
        if (cancelled) return;
        setBrands(next);
        setBrand((current) =>
          current && !next.some((b) => b.slug === current) ? "" : current,
        );
      } catch {
        if (!cancelled) setBrands([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [effectiveCategory]);

  function pushQuery(next: Record<string, string>) {
    const qs = new URLSearchParams();
    Object.entries(next).forEach(([k, v]) => {
      if (v) qs.set(k, v);
    });
    qs.delete("page");
    router.push(qs.toString() ? `${basePath}?${qs}` : basePath);
  }

  function onCategoryChange(next: string) {
    setCategory(next);
    setBrand("");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const brandAllowed =
      !brand || brands.some((b) => b.slug === brand) ? brand : "";
    const next: Record<string, string> = {
      brand: brandAllowed,
      min_price: minPrice,
      max_price: maxPrice,
      search,
      sort,
    };
    if (!lockedCategory) {
      next.category = category;
    }
    pushQuery(next);
  }

  function clearFilters() {
    if (!lockedCategory) setCategory("");
    setBrand("");
    setMinPrice("");
    setMaxPrice("");
    setSearch("");
    router.push(basePath);
  }

  const hasFilters = useMemo(
    () =>
      Boolean(
        (!lockedCategory && category) || brand || minPrice || maxPrice || search,
      ),
    [category, brand, minPrice, maxPrice, search, lockedCategory],
  );

  return (
    <form
      onSubmit={onSubmit}
      className={
        embedded
          ? "grid min-w-0 gap-4 overflow-hidden p-5"
          : "gema-panel-elevated grid min-w-0 gap-4 overflow-hidden p-6"
      }
    >
      <div className="min-w-0">
        <p className="font-display text-base font-semibold text-navy">Filtros</p>
        <p className="mt-0.5 font-mono text-xs text-muted">REFINE</p>
      </div>

      <div className="min-w-0">
        <label className="label-field" htmlFor={sid("filter-search")}>
          Buscar
        </label>
        <input
          id={sid("filter-search")}
          className="input-field mt-1.5 max-w-full min-w-0"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Nombre, SKU…"
        />
      </div>
      {!hideCategory ? (
        <div className="min-w-0">
          <label className="label-field" htmlFor={sid("filter-category")}>
            Categoría
          </label>
          <div className="mt-1.5 min-w-0">
            <CategoryPicker
              id={sid("filter-category")}
              categories={categories}
              value={category}
              onChange={onCategoryChange}
              valueKey="slug"
              emptyLabel="Todas"
              placeholder="Buscar categoría…"
              searchPlaceholder="Nombre o ruta…"
              aria-label="Filtrar por categoría"
            />
          </div>
        </div>
      ) : null}
      <div className="min-w-0">
        <label className="label-field" htmlFor={sid("filter-brand")}>
          Marca
        </label>
        <Select
          id={sid("filter-brand")}
          className="mt-1.5"
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          aria-label="Filtrar por marca"
        >
          <option value="">Todas</option>
          {brands.map((b) => (
            <option key={b.id} value={b.slug}>
              {b.name}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid min-w-0 grid-cols-2 gap-3">
        <div className="min-w-0">
          <label className="label-field" htmlFor={sid("filter-min")}>
            Precio mín.
          </label>
          <input
            id={sid("filter-min")}
            className="input-field mt-1.5 w-full max-w-full min-w-0"
            type="number"
            min={0}
            step="0.01"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            aria-label="Precio mínimo"
          />
        </div>
        <div className="min-w-0">
          <label className="label-field" htmlFor={sid("filter-max")}>
            Precio máx.
          </label>
          <input
            id={sid("filter-max")}
            className="input-field mt-1.5 w-full max-w-full min-w-0"
            type="number"
            min={0}
            step="0.01"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            aria-label="Precio máximo"
          />
        </div>
      </div>
      <div className="flex flex-col gap-2 pt-1">
        <button type="submit" className="btn-primary w-full">
          Aplicar
        </button>
        {hasFilters ? (
          <button type="button" className="btn-ghost w-full" onClick={clearFilters}>
            Limpiar filtros
          </button>
        ) : null}
      </div>
    </form>
  );
}
