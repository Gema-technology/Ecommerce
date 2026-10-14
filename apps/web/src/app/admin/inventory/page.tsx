"use client";

import { MapPin, Plus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { AdminFilterBar } from "@/components/admin/AdminFilterBar";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTable } from "@/components/admin/AdminTable";
import {
  FieldRow,
  FormModal,
  FormModalActions,
  FormSection,
} from "@/components/admin/forms/AdminFormPrimitives";
import { FormField, Input, Select } from "@/components/ui/input";
import { Pagination } from "@/components/shared/Pagination";
import { ApiError } from "@/lib/auth-api";
import { catalogApi, type Product } from "@/lib/catalog-api";
import {
  inventoryApi,
  type InventoryItem,
  type Location,
} from "@/lib/inventory-api";
import { useAdminListParams } from "@/lib/use-admin-list-params";

const INIT_FORM_ID = "inventory-init-form";

export default function AdminInventoryPage() {
  const router = useRouter();
  const list = useAdminListParams();
  const location = list.get("location");

  const [items, setItems] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [lowStock, setLowStock] = useState<InventoryItem[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [initOpen, setInitOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [initProductId, setInitProductId] = useState("");
  const [initLocationId, setInitLocationId] = useState("");
  const [initReorderPoint, setInitReorderPoint] = useState("0");
  const [initReorderQty, setInitReorderQty] = useState("0");

  const [draftQ, setDraftQ] = useState(list.q);
  const [draftLocation, setDraftLocation] = useState(location);

  useEffect(() => {
    setDraftQ(list.q);
    setDraftLocation(location);
  }, [list.q, location]);

  useEffect(() => {
    void inventoryApi
      .listAllLocations()
      .then(setLocations)
      .catch(() => {
        /* filters still work without options */
      });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const locFilter = location || undefined;
      const [all, low] = await Promise.all([
        inventoryApi.list({
          location_id: locFilter,
          q: list.q || undefined,
          page: list.page,
          page_size: list.pageSize,
        }),
        inventoryApi.lowStock(locFilter),
      ]);
      setItems(all.items);
      setTotal(all.total);
      setTotalPages(all.total_pages);
      setLowStock(low);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Error al cargar inventario",
      );
      setItems([]);
      setTotal(0);
      setTotalPages(0);
      setLowStock([]);
    } finally {
      setLoading(false);
    }
  }, [list.page, list.pageSize, list.q, location]);

  useEffect(() => {
    void load();
  }, [load]);

  function onFilter(event: FormEvent) {
    event.preventDefault();
    list.applyFilters({
      q: draftQ,
      location: draftLocation,
    });
  }

  const stats = useMemo(() => {
    const outOfStock = items.filter((i) => i.available_quantity <= 0).length;
    const withStock = items.filter((i) => i.available_quantity > 0).length;
    return {
      total,
      withStock,
      outOfStock,
      lowStock: lowStock.length,
    };
  }, [items, lowStock, total]);

  async function openInit() {
    setError(null);
    setInitProductId("");
    setInitLocationId(location || locations[0]?.id || "");
    setInitReorderPoint("0");
    setInitReorderQty("0");
    try {
      if (products.length === 0) {
        const catalog = await catalogApi.listProducts({ page_size: 100 }, true);
        setProducts(catalog.items.filter((p) => p.is_active));
      }
      setInitOpen(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudieron cargar productos",
      );
    }
  }

  async function onInit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const created = await inventoryApi.create({
        product_id: initProductId,
        location_id: initLocationId || undefined,
        reorder_point: Number(initReorderPoint) || 0,
        reorder_quantity: Number(initReorderQty) || 0,
      });
      setInitOpen(false);
      router.push(
        `/admin/inventory/${created.product_id}?location_id=${created.location.id}`,
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo inicializar",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell title="Inventario">
      <p className="mb-4 text-sm text-secondary">
        Stock, umbrales, ubicaciones y movimientos por producto.
      </p>

      <AdminFilterBar
        onSubmit={onFilter}
        onClear={() => {
          setDraftQ("");
          setDraftLocation("");
          list.clearFilters(["q", "location"]);
        }}
        actions={
          <>
            <Link href="/admin/inventory/locations" className="btn-ghost">
              <MapPin className="h-4 w-4" aria-hidden />
              Ubicaciones
            </Link>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void openInit()}
            >
              <Plus className="h-4 w-4" aria-hidden />
              Inicializar inventario
            </button>
          </>
        }
      >
        <FormField label="Buscar" className="w-56 min-w-0">
          <Input
            value={draftQ}
            onChange={(e) => setDraftQ(e.target.value)}
            placeholder="SKU o nombre"
          />
        </FormField>
        <FormField label="Ubicación" className="w-48 min-w-0">
          <Select
            value={draftLocation}
            onChange={(e) => setDraftLocation(e.target.value)}
          >
            <option value="">Todas</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name} ({loc.code})
              </option>
            ))}
          </Select>
        </FormField>
      </AdminFilterBar>

      {error ? (
        <p className="mb-4 text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="mb-8 grid gap-3 sm:grid-cols-4">
        <Stat label="Registros" value={stats.total} />
        <Stat label="Con stock" value={stats.withStock} />
        <Stat label="Agotados" value={stats.outOfStock} />
        <Stat label="Bajo stock" value={stats.lowStock} />
      </div>

      {lowStock.length > 0 ? (
        <section className="mb-8">
          <h2 className="font-display mb-3 text-lg font-semibold">
            Bajo stock
          </h2>
          <div className="gema-panel overflow-x-auto">
            <table className="gema-table">
              <thead>
                <tr>
                  <th>Producto</th>
                  <th>Ubicación</th>
                  <th>Disponible</th>
                  <th>Punto reorden</th>
                  <th>Cant. reorden</th>
                </tr>
              </thead>
              <tbody>
                {lowStock.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link
                        href={`/admin/inventory/${item.product_id}?location_id=${item.location.id}`}
                        className="text-cyan underline"
                      >
                        {item.product_sku} — {item.product_name}
                      </Link>
                    </td>
                    <td>{item.location.name}</td>
                    <td>{item.available_quantity}</td>
                    <td>{item.reorder_point}</td>
                    <td>{item.reorder_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="font-display mb-3 text-lg font-semibold">
          Stock por producto
        </h2>
        <AdminTable
          columns={8}
          loading={loading}
          isEmpty={!items.length}
          emptyMessage={
            location
              ? "No hay registros. Prueba otra ubicación o inicializa stock."
              : "No hay registros. Usa “Inicializar inventario” o registra una compra en un producto."
          }
          meta={`${total} registro${total === 1 ? "" : "s"}`}
          head={
            <tr>
              <th>SKU</th>
              <th>Producto</th>
              <th>Ubicación</th>
              <th>En bodega</th>
              <th>Reservado</th>
              <th>Disponible</th>
              <th>Punto reorden</th>
              <th />
            </tr>
          }
          footer={
            <Pagination
              page={list.page}
              totalPages={totalPages}
              total={total}
              basePath="/admin/inventory"
            />
          }
        >
          {items.map((item) => (
            <tr key={item.id}>
              <td className="font-mono text-xs">{item.product_sku}</td>
              <td>{item.product_name}</td>
              <td>
                {item.location.name}
                <span className="ml-1 font-mono text-[10px] text-muted">
                  {item.location.code}
                </span>
              </td>
              <td>{item.quantity}</td>
              <td>{item.reserved_quantity}</td>
              <td>
                {item.available_quantity}
                {item.available_quantity <= item.reorder_point ? (
                  <span className="ml-2 text-xs font-medium text-warning">
                    Bajo
                  </span>
                ) : null}
              </td>
              <td>{item.reorder_point}</td>
              <td>
                <Link
                  href={`/admin/inventory/${item.product_id}?location_id=${item.location.id}`}
                  className="btn-ghost btn-sm"
                >
                  Detalle
                </Link>
              </td>
            </tr>
          ))}
        </AdminTable>
      </section>

      <FormModal
        open={initOpen}
        onClose={() => setInitOpen(false)}
        title="Inicializar inventario"
        subtitle="Crea el registro en qty 0; el stock se ingresa con movimientos"
        footer={
          <FormModalActions
            formId={INIT_FORM_ID}
            submitLabel="Crear registro"
            saving={saving}
            onCancel={() => setInitOpen(false)}
          />
        }
      >
        <form
          id={INIT_FORM_ID}
          className="admin-form"
          onSubmit={(e) => void onInit(e)}
        >
          <FormSection label="Producto y ubicación">
            <div>
              <label className="label-field" htmlFor="init-product">
                Producto
              </label>
              <Select
                id="init-product"
                value={initProductId}
                onChange={(e) => setInitProductId(e.target.value)}
                required
              >
                <option value="">Seleccionar</option>
                {products.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.sku} — {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="label-field" htmlFor="init-location">
                Ubicación
              </label>
              <Select
                id="init-location"
                value={initLocationId}
                onChange={(e) => setInitLocationId(e.target.value)}
              >
                <option value="">Bodega principal (MAIN)</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.code})
                  </option>
                ))}
              </Select>
            </div>
            <FieldRow>
              <div>
                <label className="label-field" htmlFor="init-rp">
                  Punto de reorden
                </label>
                <input
                  id="init-rp"
                  className="input-field"
                  type="number"
                  min={0}
                  value={initReorderPoint}
                  onChange={(e) => setInitReorderPoint(e.target.value)}
                />
              </div>
              <div>
                <label className="label-field" htmlFor="init-rq">
                  Cantidad de reorden
                </label>
                <input
                  id="init-rq"
                  className="input-field"
                  type="number"
                  min={0}
                  value={initReorderQty}
                  onChange={(e) => setInitReorderQty(e.target.value)}
                />
              </div>
            </FieldRow>
          </FormSection>
        </form>
      </FormModal>
    </AdminShell>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="gema-panel p-4">
      <p className="text-sm text-secondary">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{value}</p>
    </div>
  );
}
