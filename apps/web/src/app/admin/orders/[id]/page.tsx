"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { useConfirmDialog } from "@/components/ui/confirm-dialog";
import { FormField, Input, Select } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/auth-api";
import { formatPrice } from "@/lib/catalog-types";
import {
  fulfillmentActionLabel,
  orderStatusLabel,
  ordersApi,
  type FulfillmentStatus,
  type Order,
} from "@/lib/orders-api";
import {
  fiscalStatusLabel,
  sriApi,
  type BuyerIdType,
  type FiscalDocument,
} from "@/lib/sri-api";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

function buyerIdTypeLabel(type: string | null | undefined): string {
  switch (type) {
    case "CONSUMIDOR_FINAL":
      return "Consumidor final";
    case "CEDULA":
      return "Cédula";
    case "RUC":
      return "RUC";
    case "PASAPORTE":
      return "Pasaporte";
    default:
      return type || "—";
  }
}

function buyerAddressFromOrder(order: Order): string {
  const address = order.shipping_address;
  if (!address) return "";
  return [
    address.address_line,
    address.reference,
    address.city,
    address.province,
  ]
    .filter(Boolean)
    .join(", ");
}

function orderStatusBadgeClass(status: string): string {
  switch (status) {
    case "PENDING_PAYMENT":
      return "gema-badge gema-badge-warning";
    case "PAID":
    case "PROCESSING":
      return "gema-badge gema-badge-primary";
    case "SHIPPED":
      return "gema-badge gema-badge-accent";
    case "DELIVERED":
      return "gema-badge gema-badge-success";
    case "CANCELLED":
      return "gema-badge gema-badge-error";
    default:
      return "gema-badge gema-badge-muted";
  }
}

function fiscalStatusBadgeClass(status: string): string {
  switch (status) {
    case "AUTHORIZED":
    case "ISSUED":
      return "gema-badge gema-badge-success";
    case "PENDING":
    case "SENT":
      return "gema-badge gema-badge-warning";
    case "REJECTED":
    case "CANCELLED":
      return "gema-badge gema-badge-error";
    default:
      return "gema-badge gema-badge-muted";
  }
}

function reservationStatusLabel(status: string): string {
  switch (status) {
    case "ACTIVE":
      return "Activa";
    case "CONSUMED":
      return "Consumida";
    case "RELEASED":
      return "Liberada";
    case "EXPIRED":
      return "Expirada";
    default:
      return status;
  }
}

const PAID_LIKE = new Set(["PAID", "PROCESSING", "SHIPPED", "DELIVERED"]);

function MetaRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-0.5 sm:grid-cols-[8.5rem_1fr] sm:gap-3">
      <dt className="text-secondary">{label}</dt>
      <dd className="min-w-0 break-words text-foreground">{children}</dd>
    </div>
  );
}

export default function AdminOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const toast = useToast();
  const { confirm, dialog: confirmDialog } = useConfirmDialog();
  const [order, setOrder] = useState<Order | null>(null);
  const [docs, setDocs] = useState<FiscalDocument[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [removingTax, setRemovingTax] = useState(false);
  const [fulfilling, setFulfilling] = useState(false);
  const [emitting, setEmitting] = useState(false);
  const [buyerIdType, setBuyerIdType] = useState<BuyerIdType>("CONSUMIDOR_FINAL");
  const [buyerIdNumber, setBuyerIdNumber] = useState("");
  const [buyerName, setBuyerName] = useState("");
  const [buyerEmail, setBuyerEmail] = useState("");
  const [buyerAddress, setBuyerAddress] = useState("");

  const loadDocs = useCallback(async (orderId: string) => {
    try {
      setDocs(await sriApi.listForOrder(orderId));
    } catch {
      setDocs([]);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        const o = await ordersApi.adminGet(params.id);
        setOrder(o);
        setBuyerIdType((o.buyer_id_type as BuyerIdType) || "CONSUMIDOR_FINAL");
        setBuyerIdNumber(o.buyer_id_number || "");
        setBuyerName(o.customer_name || "");
        setBuyerEmail(o.customer_email || "");
        setBuyerAddress(buyerAddressFromOrder(o));
        await loadDocs(o.id);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Pedido no encontrado");
      }
    })();
  }, [params.id, loadDocs]);

  async function cancelOrder() {
    if (!order) return;
    const ok = await confirm({
      title: "Cancelar pedido",
      description:
        "¿Cancelar este pedido pendiente? Se liberará el stock reservado.",
      confirmLabel: "Cancelar pedido",
      tone: "danger",
    });
    if (!ok) return;
    setCancelling(true);
    setError(null);
    try {
      setOrder(await ordersApi.adminCancel(order.id));
      toast.success("Pedido cancelado.");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo cancelar el pedido";
      setError(msg);
      toast.error(msg);
    } finally {
      setCancelling(false);
    }
  }

  async function removeIva() {
    if (!order) return;
    const ok = await confirm({
      title: "Quitar IVA",
      description:
        "El total queda en el valor de los productos y el envío. El efectivo de esta venta se ajusta al mismo monto.",
      confirmLabel: "Quitar IVA",
    });
    if (!ok) return;
    setRemovingTax(true);
    setError(null);
    try {
      setOrder(await ordersApi.adminRemoveIva(order.id));
      toast.success("IVA quitado del pedido.");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "No se pudo quitar el IVA";
      setError(msg);
      toast.error(msg);
    } finally {
      setRemovingTax(false);
    }
  }

  async function applyFulfillment(next: FulfillmentStatus) {
    if (!order) return;
    const label = fulfillmentActionLabel(next);
    const ok = await confirm({
      title: "Actualizar estado",
      description: `¿${label}?`,
      confirmLabel: label,
    });
    if (!ok) return;
    setFulfilling(true);
    setError(null);
    try {
      setOrder(await ordersApi.adminUpdateStatus(order.id, next));
      toast.success(`Estado actualizado: ${orderStatusLabel(next)}.`);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo actualizar el estado del pedido";
      setError(msg);
      toast.error(msg);
    } finally {
      setFulfilling(false);
    }
  }

  async function emitDoc(docType: "NOTA_VENTA" | "FACTURA") {
    if (!order) return;
    setEmitting(true);
    setError(null);
    try {
      const doc = await sriApi.emit(order.id, {
        doc_type: docType,
        buyer_id_type: buyerIdType,
        buyer_id_number:
          buyerIdType === "CONSUMIDOR_FINAL" ? null : buyerIdNumber || null,
        buyer_name: buyerName || null,
        buyer_email: buyerEmail || null,
        buyer_address: buyerAddress || null,
        send_to_sri: docType === "FACTURA",
      });
      setDocs((prev) => [doc, ...prev.filter((d) => d.id !== doc.id)]);
      setOrder(await ordersApi.adminGet(order.id));
      toast.success(
        docType === "FACTURA"
          ? "Factura emitida."
          : "Nota de venta emitida.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo emitir el comprobante";
      setError(msg);
      toast.error(msg);
    } finally {
      setEmitting(false);
    }
  }

  async function retryAuth(docId: string) {
    setError(null);
    try {
      const updated = await sriApi.retryAuthorization(docId);
      setDocs((prev) => prev.map((d) => (d.id === docId ? updated : d)));
      toast.success("Autorización reintentada.");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "No se pudo reintentar autorización";
      setError(msg);
      toast.error(msg);
    }
  }

  const canEmit =
    order &&
    PAID_LIKE.has(order.status) &&
    !docs.some((d) => !["CANCELLED", "REJECTED"].includes(d.status));

  const hasTransitions = (order?.allowed_transitions?.length ?? 0) > 0;
  const hasHistory = (order?.status_history?.length ?? 0) > 0;
  const showShipping = order && Number(order.shipping_total) > 0;
  const showTax = order && Number(order.tax_total) > 0;
  const showDiscount = order && Number(order.discount_total) > 0;

  return (
    <AdminShell title={order ? `Pedido ${order.order_number}` : "Pedido"}>
      {confirmDialog}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link href="/admin/orders" className="btn-ghost btn-sm">
          ← Pedidos
        </Link>
        {order ? (
          <>
            <span className={orderStatusBadgeClass(order.status)}>
              {orderStatusLabel(order.status)}
            </span>
            <span className="text-sm text-secondary">
              {new Date(order.created_at).toLocaleString("es-EC")}
            </span>
            <span className="ml-auto font-display text-lg font-semibold tracking-tight">
              {money(order.total, order.currency)}
            </span>
          </>
        ) : null}
      </div>

      {error ? (
        <p
          className="mb-4 rounded-md border border-error/30 bg-error/5 px-4 py-3 text-sm text-error"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {!order && !error ? (
        <p className="text-sm text-secondary">Cargando pedido…</p>
      ) : null}

      {order ? (
        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
          <div className="space-y-6">
            <section className="gema-panel p-5">
              <h2 className="font-display mb-4 text-lg font-semibold">
                Cliente
              </h2>
              <dl className="space-y-3 text-sm">
                <MetaRow label="Nombre">
                  {order.customer_name || "—"}
                </MetaRow>
                <MetaRow label="Origen">
                  {order.channel === "COUNTER" ? "Mostrador" : "Tienda web"}
                </MetaRow>
                <MetaRow label="Correo">
                  {order.customer_email ? (
                    <a
                      href={`mailto:${order.customer_email}`}
                      className="text-cyan underline-offset-2 hover:underline"
                    >
                      {order.customer_email}
                    </a>
                  ) : (
                    "—"
                  )}
                </MetaRow>
                {order.customer_phone ? (
                  <MetaRow label="Teléfono">{order.customer_phone}</MetaRow>
                ) : null}
                <MetaRow label="ID fiscal">
                  {buyerIdTypeLabel(order.buyer_id_type)}
                  {order.buyer_id_number ? (
                    <span className="ml-1 font-mono text-xs">
                      {order.buyer_id_number}
                    </span>
                  ) : null}
                </MetaRow>
                {order.reserved_until && order.status === "PENDING_PAYMENT" ? (
                  <MetaRow label="Reserva hasta">
                    {new Date(order.reserved_until).toLocaleString("es-EC")}
                  </MetaRow>
                ) : null}
              </dl>
            </section>

            {order.shipping_address ? (
              <section className="gema-panel p-5">
                <h2 className="font-display mb-4 text-lg font-semibold">
                  Entrega
                </h2>
                <dl className="space-y-3 text-sm">
                  <MetaRow label="Destinatario">
                    {order.shipping_address.recipient_name}
                  </MetaRow>
                  <MetaRow label="Teléfono">
                    <a
                      href={`tel:${order.shipping_address.phone}`}
                      className="text-cyan underline-offset-2 hover:underline"
                    >
                      {order.shipping_address.phone}
                    </a>
                  </MetaRow>
                  <MetaRow label="Dirección">
                    {order.shipping_address.address_line}
                    {order.shipping_address.reference
                      ? ` · ${order.shipping_address.reference}`
                      : ""}
                  </MetaRow>
                  <MetaRow label="Ciudad">
                    {order.shipping_address.city},{" "}
                    {order.shipping_address.province}
                  </MetaRow>
                  <MetaRow label="País">
                    {order.shipping_address.country}
                  </MetaRow>
                </dl>
                {order.customer_notes ? (
                  <div className="mt-4 rounded-md border border-border bg-surface-hover px-3 py-2 text-sm">
                    <p className="text-xs font-medium uppercase tracking-wide text-secondary">
                      Notas del cliente
                    </p>
                    <p className="mt-1 whitespace-pre-wrap">
                      {order.customer_notes}
                    </p>
                  </div>
                ) : null}
              </section>
            ) : null}

            <section className="gema-panel p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-display text-lg font-semibold">
                  Fulfillment
                </h2>
                <span className={orderStatusBadgeClass(order.status)}>
                  {orderStatusLabel(order.status)}
                </span>
              </div>

              {hasTransitions ? (
                <>
                  <p className="mb-3 text-sm text-secondary">
                    Siguiente paso desde {orderStatusLabel(order.status)}.
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {order.allowed_transitions?.map((next) => (
                      <button
                        key={next}
                        type="button"
                        className="btn-primary"
                        disabled={fulfilling || cancelling}
                        onClick={() =>
                          void applyFulfillment(next as FulfillmentStatus)
                        }
                      >
                        {fulfilling
                          ? "Actualizando…"
                          : fulfillmentActionLabel(next)}
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-sm text-secondary">
                  No hay acciones de fulfillment disponibles en este estado.
                </p>
              )}

              {order.status === "PENDING_PAYMENT" ? (
                <button
                  type="button"
                  className="btn-ghost mt-4"
                  disabled={cancelling || fulfilling}
                  onClick={() => void cancelOrder()}
                >
                  {cancelling ? "Cancelando…" : "Cancelar pedido"}
                </button>
              ) : null}

              {hasHistory ? (
                <div className="mt-6 border-t border-border pt-4">
                  <h3 className="mb-3 text-sm font-medium text-secondary">
                    Historial
                  </h3>
                  <ol className="relative space-y-4 border-l border-border pl-4">
                    {order.status_history?.map((ev) => (
                      <li key={ev.id} className="relative text-sm">
                        <span className="absolute -left-[1.3rem] top-1.5 size-2 rounded-full bg-cyan" />
                        <p className="font-medium">
                          {orderStatusLabel(ev.from_status)} →{" "}
                          {orderStatusLabel(ev.to_status)}
                        </p>
                        <p className="text-xs text-secondary">
                          {new Date(ev.created_at).toLocaleString("es-EC")}
                          {ev.note ? ` · ${ev.note}` : ""}
                        </p>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </section>
          </div>

          <div className="space-y-6">
            <section className="gema-panel overflow-hidden">
              <div className="border-b border-border px-5 py-4">
                <h2 className="font-display text-lg font-semibold">
                  Productos
                </h2>
              </div>
              <div className="overflow-x-auto">
                <table className="gema-table text-sm">
                  <thead>
                    <tr>
                      <th>Producto</th>
                      <th>SKU</th>
                      <th className="text-right">Cant.</th>
                      <th className="text-right">P. unit.</th>
                      <th className="text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.items.map((item) => (
                      <tr key={item.id}>
                        <td className="font-medium">
                          {item.product_name_snapshot}
                        </td>
                        <td className="font-mono text-xs text-secondary">
                          {item.sku_snapshot}
                        </td>
                        <td className="text-right">×{item.quantity}</td>
                        <td className="text-right">
                          {money(item.unit_price, order.currency)}
                        </td>
                        <td className="text-right font-medium">
                          {money(item.line_total, order.currency)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="space-y-2 border-t border-border px-5 py-4 text-sm">
                <div className="flex justify-between gap-4">
                  <span className="text-secondary">Subtotal</span>
                  <span>{money(order.subtotal, order.currency)}</span>
                </div>
                {showDiscount ? (
                  <div className="flex justify-between gap-4">
                    <span className="text-secondary">Descuento</span>
                    <span>-{money(order.discount_total, order.currency)}</span>
                  </div>
                ) : null}
                {showShipping ? (
                  <div className="flex justify-between gap-4">
                    <span className="text-secondary">Envío</span>
                    <span>{money(order.shipping_total, order.currency)}</span>
                  </div>
                ) : null}
                {showTax ? (
                  <div className="flex justify-between gap-4">
                    <span className="text-secondary">IVA</span>
                    <span>{money(order.tax_total, order.currency)}</span>
                  </div>
                ) : null}
                <div className="flex justify-between gap-4 border-t border-border pt-3 text-base font-semibold">
                  <span>Total</span>
                  <span>{money(order.total, order.currency)}</span>
                </div>
                {showTax ? (
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    disabled={removingTax}
                    onClick={() => void removeIva()}
                  >
                    {removingTax ? "Quitando IVA…" : "Quitar IVA"}
                  </button>
                ) : null}
              </div>
            </section>

            <section className="gema-panel p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-display text-lg font-semibold">
                  Comprobante fiscal
                </h2>
                {docs[0] ? (
                  <span className={fiscalStatusBadgeClass(docs[0].status)}>
                    {fiscalStatusLabel(docs[0].status)}
                  </span>
                ) : null}
              </div>

              {docs.length > 0 ? (
                <ul className="space-y-4">
                  {docs.map((doc) => (
                    <li
                      key={doc.id}
                      className="rounded-md border border-border px-4 py-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="font-medium">
                            {doc.doc_type === "FACTURA"
                              ? "Factura"
                              : "Nota de venta"}
                          </p>
                          <p className="font-mono text-sm text-secondary">
                            {doc.document_number}
                          </p>
                        </div>
                        <span className={fiscalStatusBadgeClass(doc.status)}>
                          {fiscalStatusLabel(doc.status)}
                        </span>
                      </div>
                      {doc.access_key ? (
                        <p className="mt-2 break-all text-xs text-secondary">
                          Clave de acceso: {doc.access_key}
                        </p>
                      ) : null}
                      {doc.sri_messages ? (
                        <p className="mt-1 text-xs text-secondary">
                          {doc.sri_messages}
                        </p>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        {doc.has_pdf ? (
                          <a
                            href={sriApi.pdfUrl(doc.id)}
                            className="btn-secondary btn-sm"
                            target="_blank"
                            rel="noreferrer"
                          >
                            Descargar PDF
                          </a>
                        ) : null}
                        {doc.has_xml ? (
                          <a
                            href={sriApi.xmlUrl(doc.id)}
                            className="btn-ghost btn-sm"
                            target="_blank"
                            rel="noreferrer"
                          >
                            XML
                          </a>
                        ) : null}
                        {doc.doc_type === "FACTURA" &&
                        doc.status !== "AUTHORIZED" ? (
                          <button
                            type="button"
                            className="btn-ghost btn-sm"
                            onClick={() => void retryAuth(doc.id)}
                          >
                            Reintentar SRI
                          </button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-secondary">
                  Aún no hay comprobante emitido para este pedido.
                </p>
              )}

              {canEmit ? (
                <div className="mt-5 space-y-4 border-t border-border pt-5">
                  <div>
                    <h3 className="font-medium">Emitir comprobante</h3>
                    <p className="mt-1 text-sm text-secondary">
                      La factura usa identificación, nombre, correo y dirección.
                      Si no hay identificación, el comprobante queda como
                      consumidor final.
                    </p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <FormField label="Tipo ID">
                      <Select
                        value={buyerIdType}
                        onChange={(e) =>
                          setBuyerIdType(e.target.value as BuyerIdType)
                        }
                      >
                        <option value="CONSUMIDOR_FINAL">
                          Consumidor final
                        </option>
                        <option value="CEDULA">Cédula</option>
                        <option value="RUC">RUC</option>
                        <option value="PASAPORTE">Pasaporte</option>
                      </Select>
                    </FormField>
                    <FormField label="Número">
                      <Input
                        disabled={buyerIdType === "CONSUMIDOR_FINAL"}
                        value={
                          buyerIdType === "CONSUMIDOR_FINAL"
                            ? "9999999999999"
                            : buyerIdNumber
                        }
                        onChange={(e) => setBuyerIdNumber(e.target.value)}
                      />
                    </FormField>
                    <FormField
                      label="Nombre / razón social"
                      className="sm:col-span-2"
                    >
                      <Input
                        value={buyerName}
                        onChange={(e) => setBuyerName(e.target.value)}
                      />
                    </FormField>
                    <FormField label="Correo">
                      <Input
                        type="email"
                        value={buyerEmail}
                        onChange={(e) => setBuyerEmail(e.target.value)}
                      />
                    </FormField>
                    <FormField label="Dirección" className="sm:col-span-2">
                      <Input
                        value={buyerAddress}
                        onChange={(e) => setBuyerAddress(e.target.value)}
                        required={buyerIdType !== "CONSUMIDOR_FINAL"}
                      />
                    </FormField>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={emitting}
                      onClick={() => void emitDoc("NOTA_VENTA")}
                    >
                      {emitting ? "Emitiendo…" : "Emitir nota de venta"}
                    </button>
                    <button
                      type="button"
                      className="btn-ghost"
                      disabled={emitting}
                      onClick={() => void emitDoc("FACTURA")}
                    >
                      Emitir factura electrónica
                    </button>
                  </div>
                  <p className="text-xs text-muted">
                    Certificado y datos del emisor en{" "}
                    <Link href="/admin/sri" className="underline">
                      Facturación SRI
                    </Link>
                    .
                  </p>
                </div>
              ) : null}
            </section>

            {(order.reservations ?? []).length > 0 ? (
              <section className="gema-panel p-5">
                <h2 className="font-display mb-4 text-lg font-semibold">
                  Reservas de stock
                </h2>
                <ul className="divide-y divide-border text-sm">
                  {(order.reservations ?? []).map((r) => (
                    <li
                      key={r.id}
                      className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0"
                    >
                      <div>
                        <p className="font-medium">Cantidad {r.quantity}</p>
                        <p className="text-xs text-secondary">
                          {r.expires_at
                            ? `Expira ${new Date(r.expires_at).toLocaleString("es-EC")}`
                            : "Sin fecha de expiración"}
                        </p>
                      </div>
                      <span className="gema-badge gema-badge-muted">
                        {reservationStatusLabel(r.status)}
                      </span>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>
        </div>
      ) : null}
    </AdminShell>
  );
}
