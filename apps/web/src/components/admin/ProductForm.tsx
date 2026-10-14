"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  FormSection,
  StatusToggle,
} from "@/components/admin/forms/AdminFormPrimitives";
import { CategoryPicker } from "@/components/categories/CategoryPicker";
import { FormField, Input, Select, Textarea } from "@/components/ui/input";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Brand, type Category } from "@/lib/catalog-api";

export type ProductFormState = {
  sku: string;
  name: string;
  short_description: string;
  description: string;
  brand_id: string;
  category_id: string;
  specifications: string;
  images: string;
  is_active: boolean;
};

export const DEFAULT_PRODUCT_FORM: ProductFormState = {
  sku: "",
  name: "",
  short_description: "",
  description: "",
  brand_id: "",
  category_id: "",
  specifications: '{\n  "ram": "16 GB"\n}',
  images:
    '[\n  {\n    "url": "https://cdn.example.com/image.jpg",\n    "alt_text": "Producto",\n    "sort_order": 0,\n    "is_primary": true\n  }\n]',
  is_active: true,
};

export function ProductForm({
  productId,
  initial,
  onSuccess,
  onCancel,
  compact,
}: {
  productId?: string;
  initial?: ProductFormState;
  onSuccess?: () => void;
  onCancel?: () => void;
  compact?: boolean;
}) {
  const router = useRouter();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<ProductFormState>(initial ?? DEFAULT_PRODUCT_FORM);

  useEffect(() => {
    if (initial) setForm(initial);
  }, [initial]);

  useEffect(() => {
    void catalogApi
      .listCategories(true)
      .then((c) => setCategories(c.filter((x) => x.is_active)))
      .catch((err) => {
        setError(err instanceof ApiError ? err.message : "Error al cargar");
      });
  }, []);

  useEffect(() => {
    const category = categories.find((c) => c.id === form.category_id);
    if (!form.category_id || !category) {
      setBrands([]);
      return;
    }
    let cancelled = false;
    void catalogApi
      .listAllBrandsAdmin({ category: category.slug })
      .then((b) => {
        if (cancelled) return;
        const active = b.filter((x) => x.is_active);
        setBrands(active);
        setForm((prev) =>
          prev.brand_id && !active.some((x) => x.id === prev.brand_id)
            ? { ...prev, brand_id: "" }
            : prev,
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Error al cargar marcas");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [form.category_id, categories]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const specifications = JSON.parse(form.specifications) as Record<string, unknown>;
      const images = JSON.parse(form.images) as unknown[];
      const payload = {
        name: form.name,
        short_description: form.short_description || null,
        description: form.description || null,
        brand_id: form.brand_id,
        category_id: form.category_id,
        specifications,
        images,
        is_active: form.is_active,
        ...(productId ? {} : { sku: form.sku }),
      };

      if (productId) {
        await catalogApi.updateProduct(productId, payload);
      } else {
        await catalogApi.createProduct(payload);
      }
      if (onSuccess) {
        onSuccess();
      } else {
        router.push("/admin/products");
      }
    } catch (err) {
      if (err instanceof SyntaxError) {
        setError("JSON inválido en especificaciones o imágenes");
      } else {
        setError(err instanceof ApiError ? err.message : "No se pudo guardar");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <form id="product-form" onSubmit={onSubmit} className="admin-form">
      <FormSection label="Información general">
        <FormField label="Nombre del producto" required>
          <Input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Ej. ASUS TUF Gaming A15"
            required
          />
        </FormField>
        {!productId ? (
          <FormField label="SKU">
            <Input
              className="mono-input"
              value={form.sku}
              onChange={(e) => setForm({ ...form, sku: e.target.value })}
              placeholder="AUTO-000"
              required
            />
          </FormField>
        ) : (
          <FormField label="SKU">
            <Input className="mono-input" value={form.sku} readOnly disabled />
          </FormField>
        )}
        <FormField label="Categoría" required>
          <CategoryPicker
            categories={categories}
            value={form.category_id}
            onChange={(category_id) =>
              setForm((prev) => ({ ...prev, category_id, brand_id: "" }))
            }
            valueKey="id"
            required
            clearable={false}
            emptyLabel="Seleccionar"
            placeholder="Buscar categoría…"
            searchPlaceholder="Nombre o ruta (ej. Impresión 3D / PLA)…"
            aria-label="Categoría del producto"
          />
        </FormField>
        <FormField
          label="Marca"
          required
          hint={
            form.category_id
              ? "Solo marcas afines a la categoría seleccionada"
              : "Elige primero una categoría"
          }
        >
          <Select
            value={form.brand_id}
            onChange={(e) => setForm({ ...form, brand_id: e.target.value })}
            required
            disabled={!form.category_id}
          >
            <option value="">
              {form.category_id ? "Seleccionar" : "Elige categoría primero"}
            </option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Descripción corta">
          <Input
            value={form.short_description}
            onChange={(e) => setForm({ ...form, short_description: e.target.value })}
            placeholder="Resumen para listados"
          />
        </FormField>
        <FormField label="Descripción">
          <Textarea
            rows={3}
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Describe brevemente el producto…"
          />
        </FormField>
      </FormSection>

      <FormSection label="Especificaciones e imágenes">
        <FormField
          label="Especificaciones (JSON)"
          hint="Pares clave-valor técnicos del producto"
        >
          <Textarea
            className="code-field"
            value={form.specifications}
            onChange={(e) => setForm({ ...form, specifications: e.target.value })}
          />
        </FormField>
        <FormField label="Imágenes (JSON)" hint="URLs, alt text, orden y primary">
          <Textarea
            className="code-field min-h-36"
            value={form.images}
            onChange={(e) => setForm({ ...form, images: e.target.value })}
          />
        </FormField>
        <div className="admin-upload-box" role="presentation">
          <div className="upload-main">Arrastra una imagen o sube vía URL en JSON</div>
          <div className="upload-sub">PNG, JPG — integración CDN próximamente</div>
        </div>
      </FormSection>

      <FormSection label="Estado">
        <StatusToggle
          label="Producto activo"
          sublabel="Visible en la tienda cuando está activo"
          checked={form.is_active}
          onChange={(is_active) => setForm({ ...form, is_active })}
        />
      </FormSection>

      {error ? (
        <p className="text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}

      {!compact ? (
        <div className="form-actions">
          {onCancel ? (
            <button type="button" className="btn-ghost" onClick={onCancel}>
              Cancelar
            </button>
          ) : null}
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Guardando…" : productId ? "Guardar cambios" : "Crear producto"}
          </button>
        </div>
      ) : null}

      {productId && compact ? (
        <p className="admin-form-hint">
          <Link href={`/admin/products/${productId}`} className="text-cyan underline">
            Precios, proveedores e inventario →
          </Link>
        </p>
      ) : null}
    </form>
  );
}

/** Footer actions when the form lives inside FormModal */
export function ProductFormFooter({
  productId,
  saving,
  onCancel,
}: {
  productId?: string;
  saving?: boolean;
  onCancel: () => void;
}) {
  return (
    <>
      <button type="button" className="btn-ghost" onClick={onCancel}>
        Cancelar
      </button>
      <button type="submit" form="product-form" className="btn-primary" disabled={saving}>
        {saving ? "Guardando…" : productId ? "Guardar producto" : "Guardar producto"}
      </button>
    </>
  );
}
