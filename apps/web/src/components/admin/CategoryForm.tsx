"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";

import { ImageUrlField } from "@/components/admin/ImageUrlField";
import { FormSection } from "@/components/admin/forms/AdminFormPrimitives";
import { CategoryPicker } from "@/components/categories/CategoryPicker";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Category } from "@/lib/catalog-api";
import { getCategoryPathLabel } from "@/lib/category-tree";

export const CATEGORY_FORM_ID = "category-form";

export function CategoryForm({
  category,
  categories,
  defaultParentId = null,
  onSuccess,
  onError,
  onSavingChange,
}: {
  category?: Category | null;
  categories: Category[];
  /** When creating, pre-select this parent (e.g. from tree "+"). */
  defaultParentId?: string | null;
  onSuccess: () => void;
  onError?: (message: string) => void;
  onSavingChange?: (saving: boolean) => void;
}) {
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(category?.name ?? "");
    setParentId(category?.parent_id ?? defaultParentId ?? "");
    setImageUrl(category?.image_url ?? "");
    setDescription(category?.description ?? "");
    setError(null);
  }, [category, defaultParentId]);

  const parentHint = useMemo(() => {
    if (!parentId) return null;
    const parent = categories.find((c) => c.id === parentId);
    if (!parent) return null;
    return getCategoryPathLabel(parent, categories);
  }, [parentId, categories]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    onSavingChange?.(true);
    try {
      const payload = {
        name: name.trim(),
        parent_id: parentId || null,
        image_url: imageUrl.trim() || null,
        description: description.trim() || null,
      };
      if (category) {
        await catalogApi.updateCategory(category.id, payload);
      } else {
        await catalogApi.createCategory(payload);
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
    <form
      id={CATEGORY_FORM_ID}
      className="admin-form"
      onSubmit={(e) => void onSubmit(e)}
    >
      <FormSection label="Información">
        <div>
          <label className="label-field" htmlFor="category-name">
            Nombre
          </label>
          <input
            id="category-name"
            className="input-field"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
            placeholder="Ej. Filamentos PLA"
          />
        </div>
        <div>
          <label className="label-field" htmlFor="category-desc">
            Descripción{" "}
            <span className="font-normal text-muted">(opcional)</span>
          </label>
          <textarea
            id="category-desc"
            className="textarea-field"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Breve texto para la tienda"
          />
        </div>
        <div>
          <label className="label-field" htmlFor="category-parent">
            Categoría padre
          </label>
          <div className="mt-1.5">
            <CategoryPicker
              id="category-parent"
              categories={categories}
              value={parentId}
              onChange={setParentId}
              valueKey="id"
              activeOnly={false}
              excludeSubtreeOf={category?.id ?? null}
              emptyLabel="— Raíz (sin padre) —"
              placeholder="Buscar categoría padre…"
              searchPlaceholder="Nombre o ruta (ej. Impresión 3D / PLA)…"
              aria-label="Categoría padre"
            />
          </div>
          {parentHint ? (
            <p className="admin-form-hint">
              Ubicación:{" "}
              <span className="font-medium text-foreground">{parentHint}</span>
            </p>
          ) : (
            <p className="admin-form-hint">
              Raíz = familia principal. Elige un padre para crear una
              subcategoría.
            </p>
          )}
        </div>
        <ImageUrlField
          id="category-image"
          label="Imagen (URL)"
          value={imageUrl}
          onChange={setImageUrl}
          placeholder="https://cdn.ejemplo.com/categoria.jpg"
        />
      </FormSection>
      {error ? (
        <p className="text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}
    </form>
  );
}
