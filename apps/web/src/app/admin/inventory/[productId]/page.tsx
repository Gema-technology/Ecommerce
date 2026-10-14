"use client";

import { Plus, Settings2 } from "lucide-react";
import Link from "next/link";
import {
  FormEvent,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import {
  FieldRow,
  FormModal,
  FormModalActions,
  FormSection,
} from "@/components/admin/forms/AdminFormPrimitives";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/auth-api";
import {
  inventoryApi,
  movementTypeLabel,
  type InventoryItem,
  type InventoryMovement,
  type Location,
  type MovementListResponse,
} from "@/lib/inventory-api";

type Op =
  | "purchase"
  | "sale"
  | "adjust"
  | "reserve"
  | "release"
  | "return"
  | "damage";

const THRESHOLDS_FORM_ID = "inventory-thresholds-form";
const MOVEMENT_FORM_ID = "inventory-movement-form";
const PAGE_SIZE = 20;

export default function InventoryDetailPage() {
  const params = useParams<{ productId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const productId = params.productId;

  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState(searchParams.get("location_id") ?? "");
  const [inventory, setInventory] = useState<InventoryItem | null>(null);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [movementMeta, setMovementMeta] = useState<Pick<
    MovementListResponse,
    "page" | "total" | "total_pages"
  >>({ page: 1, total: 0, total_pages: 0 });
  const [movementType, setMovementType] = useState("");
  const [movementPage, setMovementPage] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [thresholdsOpen, setThresholdsOpen] = useState(false);
  const [movementOpen, setMovementOpen] = useState(false);
  const [savingThresholds, setSavingThresholds] = useState(false);
  const [savingMovement, setSavingMovement] = useState(false);
  const [op, setOp] = useState<Op>("purchase");
  const [amount, setAmount] = useState("1");
  const [notes, setNotes] = useState("");
  const [referenceType, setReferenceType] = useState("");
  const [referenceId, setReferenceId] = useState("");
  const [reorderPoint, setReorderPoint] = useState("0");
  const [reorderQty, setReorderQty] = useState("0");

  const refreshInventory = useCallback(async () => {
    const loc = locationId || undefined;
    try {
      const inv = await inventoryApi.get(productId, loc);
      setInventory(inv);
      setReorderPoint(String(inv.reorder_point));
      setReorderQty(String(inv.reorder_quantity));
      if (!locationId) {
        setLocationId(inv.location.id);
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        const created = await inventoryApi.create({
          product_id: productId,
          location_id: loc,
          reorder_point: 0,
          reorder_quantity: 0,
        });
        setInventory(created);
        setLocationId(created.location.id);
        setReorderPoint("0");
        setReorderQty("0");
      } else {
        throw err;
      }
    }
  }, [productId, locationId]);

  const refreshMovements = useCallback(async () => {
    const history = await inventoryApi.movements(productId, {
      location_id: locationId || undefined,
      movement_type: movementType || undefined,
      page: movementPage,
      page_size: PAGE_SIZE,
    });
    setMovements(history.items);
    setMovementMeta({
      page: history.page,
      total: history.total,
      total_pages: history.total_pages,
    });
  }, [productId, locationId, movementType, movementPage]);

  useEffect(() => {
    void inventoryApi
      .listAllLocations()
      .then(setLocations)
      .catch(() => setLocations([]));
  }, []);

  useEffect(() => {
    void (async () => {
      setError(null);
      await refreshInventory();
      await refreshMovements();
    })().catch((err) => {
      setError(err instanceof ApiError ? err.message : "Error al cargar");
    });
  }, [refreshInventory, refreshMovements]);

  function onLocationChange(next: string) {
    setLocationId(next);
    setMovementPage(1);
    const qs = new URLSearchParams();
    if (next) qs.set("location_id", next);
    router.replace(
      qs.toString()
        ? `/admin/inventory/${productId}?${qs}`
        : `/admin/inventory/${productId}`,
    );
  }

  function openMovement() {
    setOp("purchase");
    setAmount("1");
    setNotes("");
    setReferenceType("");
    setReferenceId("");
    setMovementOpen(true);
  }

  function openThresholds() {
    if (inventory) {
      setReorderPoint(String(inventory.reorder_point));
      setReorderQty(String(inventory.reorder_quantity));
    }
    setThresholdsOpen(true);
  }

  async function onOperate(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSavingMovement(true);
    const value = Number(amount);
    const payload = {
      quantity: value,
      location_id: locationId || undefined,
      notes: notes || undefined,
      reference_type: referenceType.trim() || undefined,
      reference_id: referenceId.trim() || undefined,
    };
    try {
      if (op === "adjust") {
        await inventoryApi.adjust(productId, {
          delta: value,
          location_id: locationId || undefined,
          notes: notes || undefined,
          reference_type: referenceType.trim() || undefined,
          reference_id: referenceId.trim() || undefined,
        });
      } else if (op === "purchase") {
        await inventoryApi.purchase(productId, payload);
      } else if (op === "sale") {
        await inventoryApi.sale(productId, payload);
      } else if (op === "reserve") {
        await inventoryApi.reserve(productId, payload);
      } else if (op === "release") {
        await inventoryApi.release(productId, payload);
      } else if (op === "return") {
        await inventoryApi.returnStock(productId, payload);
      } else {
        await inventoryApi.damage(productId, payload);
      }
      setMovementOpen(false);
      await refreshInventory();
      await refreshMovements();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Operación fallida");
    } finally {
      setSavingMovement(false);
    }
  }

  async function onSaveThresholds(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSavingThresholds(true);
    try {
      const updated = await inventoryApi.updateThresholds(
        productId,
        {
          reorder_point: Number(reorderPoint),
          reorder_quantity: Number(reorderQty),
        },
        locationId || undefined,
      );
      setInventory(updated);
      setThresholdsOpen(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setSavingThresholds(false);
    }
  }

  return (
    <AdminShell title={inventory ? inventory.product_name : "Inventario"}>
      <div className="mb-6">
        <Link href="/admin/inventory" className="btn-ghost btn-sm">
          ← Volver a inventario
        </Link>
      </div>

      {error ? (
        <p className="mb-4 text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="mb-6 max-w-sm">
        <label className="label-field" htmlFor="detail-location">
          Ubicación
        </label>
        <Select
          id="detail-location"
          className="mt-1.5"
          value={locationId}
          onChange={(e) => onLocationChange(e.target.value)}
          aria-label="Ubicación de inventario"
        >
          {locations.length === 0 ? (
            <option value={locationId}>Cargando…</option>
          ) : (
            locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name} ({loc.code})
              </option>
            ))
          )}
        </Select>
        <p className="mt-1 text-xs text-muted">
          El checkout reserva stock solo en MAIN (Bodega Principal).
        </p>
      </div>

      {inventory ? (
        <>
          <section className="mb-8 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
            <Info label="SKU" value={inventory.product_sku} />
            <Info
              label="Ubicación"
              value={`${inventory.location.name} (${inventory.location.code})`}
            />
            <Info label="En bodega" value={String(inventory.quantity)} />
            <Info label="Reservado" value={String(inventory.reserved_quantity)} />
            <Info label="Disponible" value={String(inventory.available_quantity)} />
            <Info label="Punto de reorden" value={String(inventory.reorder_point)} />
            <Info label="Cantidad de reorden" value={String(inventory.reorder_quantity)} />
            <Info
              label="Producto"
              value={
                <Link
                  href={`/admin/products/${inventory.product_id}`}
                  className="text-cyan underline"
                >
                  Ver ficha
                </Link>
              }
            />
          </section>

          <div className="mb-6 flex flex-wrap items-center gap-2">
            <button type="button" className="btn-secondary" onClick={openThresholds}>
              <Settings2 className="h-4 w-4" aria-hidden />
              Umbrales
            </button>
            <button type="button" className="btn-primary" onClick={openMovement}>
              <Plus className="h-4 w-4" aria-hidden />
              Nuevo movimiento
            </button>
          </div>

          <section>
            <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
              <h2 className="font-display text-lg font-semibold">
                Historial de movimientos
              </h2>
              <div className="w-full max-w-xs">
                <label className="label-field" htmlFor="movement-type-filter">
                  Filtrar tipo
                </label>
                <Select
                  id="movement-type-filter"
                  className="mt-1.5"
                  value={movementType}
                  onChange={(e) => {
                    setMovementType(e.target.value);
                    setMovementPage(1);
                  }}
                  aria-label="Filtrar tipo de movimiento"
                >
                  <option value="">Todos</option>
                  <option value="PURCHASE">Compra / ingreso</option>
                  <option value="SALE">Venta manual</option>
                  <option value="ADJUSTMENT">Ajuste</option>
                  <option value="RESERVATION">Reserva</option>
                  <option value="RELEASE">Liberación</option>
                  <option value="RETURN">Devolución</option>
                  <option value="DAMAGE">Daño / merma</option>
                </Select>
              </div>
            </div>
            <div className="gema-panel overflow-x-auto">
              <table className="gema-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Tipo</th>
                    <th>Cantidad</th>
                    <th>Referencia</th>
                    <th>Usuario</th>
                    <th>Notas</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-6 text-center text-sm text-secondary">
                        Sin movimientos en esta ubicación
                        {movementType ? " para el filtro elegido" : ""}.
                      </td>
                    </tr>
                  ) : (
                    movements.map((m) => (
                      <tr key={m.id}>
                        <td className="text-xs">
                          {new Date(m.created_at).toLocaleString()}
                        </td>
                        <td>{movementTypeLabel(m.type)}</td>
                        <td>{m.signed_quantity}</td>
                        <td className="text-xs">
                          {m.reference_type
                            ? `${m.reference_type}:${m.reference_id ?? ""}`
                            : "—"}
                        </td>
                        <td className="text-xs">
                          {m.created_by_email ?? m.created_by}
                        </td>
                        <td>{m.notes ?? "—"}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            {movementMeta.total_pages > 1 ? (
              <div className="mt-3 flex items-center justify-between gap-3 text-sm">
                <p className="text-secondary">
                  Página {movementMeta.page} de {movementMeta.total_pages} ·{" "}
                  {movementMeta.total} movimientos
                </p>
                <div className="flex gap-2">
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    disabled={movementPage <= 1}
                    onClick={() => setMovementPage((p) => Math.max(1, p - 1))}
                  >
                    Anterior
                  </button>
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    disabled={movementPage >= movementMeta.total_pages}
                    onClick={() => setMovementPage((p) => p + 1)}
                  >
                    Siguiente
                  </button>
                </div>
              </div>
            ) : null}
          </section>

          <FormModal
            open={thresholdsOpen}
            onClose={() => setThresholdsOpen(false)}
            title="Umbrales de reorden"
            subtitle={inventory.product_sku}
            footer={
              <FormModalActions
                formId={THRESHOLDS_FORM_ID}
                submitLabel="Guardar umbrales"
                saving={savingThresholds}
                onCancel={() => setThresholdsOpen(false)}
              />
            }
          >
            <form
              id={THRESHOLDS_FORM_ID}
              className="admin-form"
              onSubmit={(e) => void onSaveThresholds(e)}
            >
              <FormSection label="Reorden">
                <FieldRow>
                  <div>
                    <label className="label-field" htmlFor="rp">
                      Punto de reorden
                    </label>
                    <input
                      id="rp"
                      className="input-field"
                      type="number"
                      min={0}
                      value={reorderPoint}
                      onChange={(e) => setReorderPoint(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="label-field" htmlFor="rq">
                      Cantidad de reorden
                    </label>
                    <input
                      id="rq"
                      className="input-field"
                      type="number"
                      min={0}
                      value={reorderQty}
                      onChange={(e) => setReorderQty(e.target.value)}
                    />
                  </div>
                </FieldRow>
              </FormSection>
            </form>
          </FormModal>

          <FormModal
            open={movementOpen}
            onClose={() => setMovementOpen(false)}
            title="Nuevo movimiento"
            subtitle={`${inventory.product_sku} · ${inventory.location.code}`}
            footer={
              <FormModalActions
                formId={MOVEMENT_FORM_ID}
                submitLabel="Ejecutar"
                saving={savingMovement}
                onCancel={() => setMovementOpen(false)}
              />
            }
          >
            <form
              id={MOVEMENT_FORM_ID}
              className="admin-form"
              onSubmit={(e) => void onOperate(e)}
            >
              <FormSection label="Operación">
                <div>
                  <label className="label-field" htmlFor="op">
                    Tipo
                  </label>
                  <Select
                    id="op"
                    value={op}
                    onChange={(e) => setOp(e.target.value as Op)}
                  >
                    <option value="purchase">Compra / ingreso</option>
                    <option value="sale">Venta manual</option>
                    <option value="adjust">Ajuste (+/-)</option>
                    <option value="reserve">Reserva</option>
                    <option value="release">Liberación</option>
                    <option value="return">Devolución</option>
                    <option value="damage">Daño / merma</option>
                  </Select>
                  {op === "reserve" || op === "release" ? (
                    <p className="mt-1 text-xs text-muted">
                      Las reservas de checkout se gestionan con la orden; esto es
                      ajuste manual de stock reservado.
                    </p>
                  ) : null}
                  {op === "sale" ? (
                    <p className="mt-1 text-xs text-muted">
                      Las ventas de tienda consumen stock al confirmar el pago.
                      Usa venta manual solo para salidas fuera de checkout.
                    </p>
                  ) : null}
                </div>
                <div>
                  <label className="label-field" htmlFor="amount">
                    {op === "adjust" ? "Delta (puede ser negativo)" : "Cantidad"}
                  </label>
                  <input
                    id="amount"
                    className="input-field"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    required
                  />
                </div>
                <FieldRow>
                  <div>
                    <label className="label-field" htmlFor="ref-type">
                      Tipo referencia (opcional)
                    </label>
                    <input
                      id="ref-type"
                      className="input-field"
                      value={referenceType}
                      onChange={(e) => setReferenceType(e.target.value)}
                      placeholder="order, po…"
                    />
                  </div>
                  <div>
                    <label className="label-field" htmlFor="ref-id">
                      ID referencia (opcional)
                    </label>
                    <input
                      id="ref-id"
                      className="input-field"
                      value={referenceId}
                      onChange={(e) => setReferenceId(e.target.value)}
                    />
                  </div>
                </FieldRow>
                <div>
                  <label className="label-field" htmlFor="notes">
                    Notas
                  </label>
                  <input
                    id="notes"
                    className="input-field"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                  />
                </div>
              </FormSection>
            </form>
          </FormModal>
        </>
      ) : null}
    </AdminShell>
  );
}

function Info({
  label,
  value,
}: {
  label: string;
  value: string | ReactNode;
}) {
  return (
    <div>
      <p className="text-muted">{label}</p>
      <p className="font-medium text-foreground">{value}</p>
    </div>
  );
}
