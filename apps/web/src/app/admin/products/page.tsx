"use client";

import { Pencil, Plus } from "lucide-react";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import { FormModal } from "@/components/admin/forms/AdminFormPrimitives";
import {
  DEFAULT_PRODUCT_FORM,
  ProductForm,
  ProductFormFooter,
  type ProductFormState,
} from "@/components/admin/ProductForm";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import {
  catalogApi,
  type Brand,
  type Category,
  type Product,
} from "@/lib/catalog-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

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

export default function AdminProductsPage() {
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const list = useAdminListParams();
  const brand = list.get("brand");
  const category = list.get("category");
  const active = list.get("active");

  const [items, setItems] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);
  const [formInitial, setFormInitial] = useState<ProductFormState>(
    DEFAULT_PRODUCT_FORM,
  );

  const [draftQ, setDraftQ] = useState(list.q);
  const [draftBrand, setDraftBrand] = useState(brand);
  const [draftCategory, setDraftCategory] = useState(category);
  const [draftActive, setDraftActive] = useState(active);

  useEffect(() => {
    setDraftQ(list.q);
    setDraftBrand(brand);
    setDraftCategory(category);
    setDraftActive(active);
  }, [list.q, brand, category, active]);

  useEffect(() => {
    void Promise.all([
      catalogApi.listAllBrandsAdmin(),
      catalogApi.listCategories(true),
    ])
      .then(([b, c]) => {
        setBrands(b);
        setCategories(c);
      })
      .catch(() => {
        /* filters still work without options */
      });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await catalogApi.listProducts(
        {
          page: list.page,
          page_size: list.pageSize,
          search: list.q || undefined,
          brand: brand || undefined,
          category: category || undefined,
          is_active:
            active === "true" ? true : active === "false" ? false : undefined,
        },
        true,
      );
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
      setItems([]);
      setTotal(0);
      setTotalPages(0);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, brand, category, active]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      q: draftQ,
      brand: draftBrand,
      category: draftCategory,
      active: draftActive,
    });
  }

  function openCreate() {
    setEditingProduct(null);
    setFormInitial(DEFAULT_PRODUCT_FORM);
    setModalOpen(true);
  }

  function openEdit(product: Product) {
    setEditingProduct(product);
    setFormInitial(productToForm(product));
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setEditingProduct(null);
  }

  async function toggleActive(product: Product) {
    if (product.is_active) {
      const ok = await confirm({
        title: "Desactivar producto",
        description: `¿Desactivar «${product.name}»? Dejará de mostrarse en la tienda.`,
        confirmLabel: "Desactivar",
        tone: "danger",
      });
      if (!ok) return;
    }
    setError(null);
    try {
      if (product.is_active) {
        await catalogApi.deleteProduct(product.id);
        toast.success("Producto desactivado.");
      } else {
        await catalogApi.updateProduct(product.id, { is_active: true });
        toast.success("Producto activado.");
      }
      await load();
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo actualizar";
      setError(msg);
      toast.error(msg);
    }
  }

  return (
    <AdminShell title="Productos">
      {confirmDialog}
      <p className="mb-4 text-sm text-secondary">
        Gestiona el catálogo, precios e inventario de tu tienda.
      </p>

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftBrand("");
          setDraftCategory("");
          setDraftActive("");
          list.clearFilters(["q", "brand", "category", "active"]);
        }}
        actions={
          <button type="button" className="btn-primary" onClick={openCreate}>
            <Plus className="h-4 w-4" aria-hidden />
            Nuevo producto
          </button>
        }
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="SKU o nombre"
          />
        </FormField>
        <FormField label="Marca" className="w-44 min-w-0">
          <Select
            value={draftBrand}
            onChange={(e) => setDraftBrand(e.target.value)}
          >
            <option value="">Todas</option>
            {brands.map((b) => (
              <option key={b.id} value={b.slug}>
                {b.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Categoría" className="w-44 min-w-0">
          <Select
            value={draftCategory}
            onChange={(e) => setDraftCategory(e.target.value)}
          >
            <option value="">Todas</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>
                {c.name}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label="Estado" className="w-36 min-w-0">
          <Select
            value={draftActive}
            onChange={(e) => setDraftActive(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="true">Activos</option>
            <option value="false">Inactivos</option>
          </Select>
        </FormField>
      </AdminFilterBar>

      <AdminTable
        columns={6}
        loading={loading}
        error={error}
        isEmpty={!items.length}
        emptyMessage="No hay productos."
        meta={`${total} producto${total === 1 ? "" : "s"}`}
        head={
          <tr>
            <th>SKU</th>
            <th>Nombre</th>
            <th>Marca</th>
            <th>Categoría</th>
            <th>Estado</th>
            <th>Acciones</th>
          </tr>
        }
        footer={
          <Pagination
            page={list.page}
            totalPages={totalPages}
            total={total}
            basePath="/admin/products"
          />
        }
      >
        {items.map((item) => (
          <tr key={item.id}>
            <td className="font-mono text-xs">{item.sku}</td>
            <td className="font-medium">{item.name}</td>
            <td>{item.brand.name}</td>
            <td>
              <span className="font-mono rounded-full border border-border px-2 py-0.5 text-[10.5px] text-secondary">
                {item.category.name}
              </span>
            </td>
            <td>{item.is_active ? "Activo" : "Inactivo"}</td>
            <td>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => openEdit(item)}
                >
                  <Pencil className="mr-1 inline h-3 w-3" aria-hidden />
                  Editar
                </button>
                <Link
                  href={`/admin/products/${item.id}`}
                  className="btn-ghost btn-sm"
                >
                  Avanzado
                </Link>
                <button
                  type="button"
                  className="btn-ghost btn-sm"
                  onClick={() => void toggleActive(item)}
                >
                  {item.is_active ? "Desactivar" : "Activar"}
                </button>
              </div>
            </td>
          </tr>
        ))}
      </AdminTable>

      <FormModal
        open={modalOpen}
        onClose={closeModal}
        size="lg"
        title={editingProduct ? "Editar producto" : "Nuevo producto"}
        subtitle={
          editingProduct ? editingProduct.sku : "SKU se genera al guardar"
        }
        footer={
          <ProductFormFooter
            productId={editingProduct?.id}
            onCancel={closeModal}
          />
        }
      >
        <ProductForm
          key={editingProduct?.id ?? "new"}
          productId={editingProduct?.id}
          initial={formInitial}
          compact
          onSuccess={() => {
            closeModal();
            void load();
          }}
          onCancel={closeModal}
        />
      </FormModal>
    </AdminShell>
  );
}
