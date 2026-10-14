"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ImageUrlField } from "@/components/admin/ImageUrlField";
import { FormSection } from "@/components/admin/forms/AdminFormPrimitives";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Brand, type Category } from "@/lib/catalog-api";
import { flattenCategories } from "@/lib/category-tree";

export const BRAND_FORM_ID = "brand-form";

export function BrandForm({
  brand,
  onSuccess,
  onError,
  onSavingChange,
}: {
  brand?: Brand | null;
  onSuccess: () => void;
  onError?: (message: string) => void;
  onSavingChange?: (saving: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [website, setWebsite] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [categoryIds, setCategoryIds] = useState<string[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(brand?.name ?? "");
    setWebsite(brand?.website_url ?? "");
    setLogoUrl(brand?.logo_url ?? "");
    setCategoryIds(brand?.category_ids ?? []);
    setError(null);
  }, [brand]);

  useEffect(() => {
    void catalogApi
      .listCategories(true)
      .then((items) => setCategories(items.filter((c) => c.is_active)))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Error al cargar categorías");
      });
  }, []);

  const flatCategories = useMemo(
    () => flattenCategories(categories),
    [categories],
  );

  function toggleCategory(id: string) {
    setCategoryIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    onSavingChange?.(true);
    try {
      const payload = {
        name,
        website_url: website.trim() || null,
        logo_url: logoUrl.trim() || null,
        category_ids: categoryIds,
      };
      if (brand) {
        await catalogApi.updateBrand(brand.id, payload);
      } else {
        await catalogApi.createBrand(payload);
      }
      onSuccess();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "No se pudo guardar";
      setError(message);
      onError?.(message);
    } finally {
      onSavingChange?.(false);
    }
  }

  return (
    <form id={BRAND_FORM_ID} className="admin-form" onSubmit={(e) => void onSubmit(e)}>
      <FormSection label="Información">
        <div>
          <label className="label-field" htmlFor="brand-name">
            Nombre
          </label>
          <input
            id="brand-name"
            className="input-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
        </div>
        <ImageUrlField
          id="brand-logo"
          label="Logo (URL)"
          value={logoUrl}
          onChange={setLogoUrl}
          placeholder="https://cdn.ejemplo.com/logo-dell.png"
        />
        <div>
          <label className="label-field" htmlFor="brand-website">
            Sitio web
          </label>
          <input
            id="brand-website"
            className="input-field"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
            placeholder="https://ejemplo.com"
          />
        </div>
      </FormSection>

      <FormSection label="Categorías que maneja">
        <p className="mb-2 text-sm text-secondary">
          La marca aplica a cada categoría seleccionada y a todos sus hijos en el
          árbol.
        </p>
        {flatCategories.length === 0 ? (
          <p className="text-sm text-muted">No hay categorías activas.</p>
        ) : (
          <ul className="max-h-56 space-y-1.5 overflow-y-auto rounded-[var(--radius-sm)] border border-border p-3">
            {flatCategories.map((cat) => {
              const checked = categoryIds.includes(cat.id);
              return (
                <li key={cat.id} style={{ paddingLeft: `${cat.depth * 0.75}rem` }}>
                  <label className="flex cursor-pointer items-center gap-2 text-sm text-navy">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleCategory(cat.id)}
                      className="accent-[var(--color-cyan)]"
                    />
                    <span>{cat.label}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        )}
      </FormSection>

      {error ? (
        <p className="text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}
