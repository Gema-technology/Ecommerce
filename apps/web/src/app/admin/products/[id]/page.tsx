"use client";

import { Pencil, Warehouse } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import {
  FormModal,
} from "@/components/admin/forms/AdminFormPrimitives";
import {
  DEFAULT_PRODUCT_FORM,
  ProductForm,
  ProductFormFooter,
  type ProductFormState,
} from "@/components/admin/ProductForm";
import { ProductPricingPanel } from "@/components/admin/ProductPricingPanel";
import { ProductSuppliersPanel } from "@/components/admin/ProductSuppliersPanel";
import { AppLoading } from "@/components/shared/AppLoading";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Product } from "@/lib/catalog-api";

function productToForm(product: Product): ProductFormState {
  return {
    sku: product.sku,
    name: product.name,
    short_description: product.short_description ?? "",
    description: product.description ?? "",
    brand_id: product.brand.id,
    category_id: product.category.id,
    specifications: JSON.stringify(product.specifications ?? {}, null, 2),
    images: JSON.stringify(
      product.images.map((img) => ({
        url: img.url,
        alt_text: img.alt_text,
        sort_order: img.sort_order,
        is_primary: img.is_primary,
      })),
      null,
      2,
    ),
    is_active: product.is_active,
  };
}

export default function EditProductPage() {
  const params = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editOpen, setEditOpen] = useState(false);
  const [formInitial, setFormInitial] = useState<ProductFormState>(DEFAULT_PRODUCT_FORM);

  const load = useCallback(async () => {
    const list = await catalogApi.listProducts({ page_size: 100 }, true);
    const found = list.items.find((p) => p.id === params.id);
    if (!found) {
      setError("Producto no encontrado");
      setProduct(null);
      return;
    }
    setProduct(found);
    setFormInitial(productToForm(found));
    setError(null);
  }, [params.id]);

  useEffect(() => {
    void load().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    });
  }, [load]);

  if (!product && !error) {
    return (
      <AdminShell title="Editar producto">
        <AppLoading compact label="Cargando producto" hideHint className="!py-12" />
      </AdminShell>
    );
  }

  return (
    <AdminShell title={product?.name ?? "Editar producto"}>
      <div className="mb-6">
        <Link href="/admin/products" className="btn-ghost btn-sm">
          ← Volver a productos
        </Link>
      </div>

      {error ? <p className="mb-4 text-sm font-medium text-error">{error}</p> : null}

      {product ? (
        <>
          <section className="gema-panel mb-8 p-5 sm:p-6">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="font-mono text-xs text-muted">{product.sku}</p>
                <h2 className="mt-1 font-display text-xl font-semibold text-navy">
                  {product.name}
                </h2>
                <p className="mt-1 text-sm text-secondary">
                  {product.brand.name} · {product.category.name}
                  {" · "}
                  {product.is_active ? "Activo" : "Inactivo"}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/admin/inventory/${product.id}`}
                  className="btn-secondary"
                >
                  <Warehouse className="h-4 w-4" aria-hidden />
                  Inventario
                </Link>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => {
                    setFormInitial(productToForm(product));
                    setEditOpen(true);
                  }}
                >
                  <Pencil className="h-4 w-4" aria-hidden />
                  Editar datos
                </button>
              </div>
            </div>
            {product.short_description ? (
              <p className="text-sm text-secondary">{product.short_description}</p>
            ) : null}
          </section>

          <ProductPricingPanel productId={params.id} />
          <ProductSuppliersPanel productId={params.id} />

          <FormModal
            open={editOpen}
            onClose={() => setEditOpen(false)}
            size="lg"
            title="Editar producto"
            subtitle={product.sku}
            footer={
              <ProductFormFooter productId={product.id} onCancel={() => setEditOpen(false)} />
            }
          >
            <ProductForm
              key={product.id}
              productId={product.id}
              initial={formInitial}
              compact
              onSuccess={() => {
                setEditOpen(false);
                void load();
              }}
              onCancel={() => setEditOpen(false)}
            />
          </FormModal>
        </>
      ) : null}
    </AdminShell>
  );
}
