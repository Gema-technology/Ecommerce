"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { FormField, Input, Select } from "@/components/ui/input";
import { adminCustomersApi, type Customer } from "@/lib/admin-customers-api";
import { ApiError } from "@/lib/auth-api";
import { catalogApi } from "@/lib/catalog-api";
import { citiesForProvince, ECUADOR_PROVINCES } from "@/lib/checkout-types";
import { formatMoneyAmount, formatPrice, type Product } from "@/lib/catalog-types";
import { ordersApi, type CounterSalePreview } from "@/lib/orders-api";

function money(amount: string, currency = "USD") {
  return formatMoneyAmount(amount, currency) ?? `${currency} ${amount}`;
}

function saleError(err: unknown): string {
  if (!(err instanceof ApiError)) return "No se pudo calcular la venta";
  if (err.message.startsWith("Price unavailable")) {
    return "Este producto no tiene precio de venta.";
  }
  if (err.message === "Product unavailable") {
    return "El producto no está disponible.";
  }
  return err.message;
}

type Line = {
  productId: string;
  name: string;
  sku: string;
  quantity: number;
  unitPrice: string | null;
};

export default function NewCounterSalePage() {
  const router = useRouter();
  const [customerQuery, setCustomerQuery] = useState("");
  const [customerResults, setCustomerResults] = useState<Customer[]>([]);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [walkInName, setWalkInName] = useState("");
  const [walkInPhone, setWalkInPhone] = useState("");
  const [buyerIdType, setBuyerIdType] = useState("");
  const [buyerIdNumber, setBuyerIdNumber] = useState("");
  const [addressLine, setAddressLine] = useState("");
  const [addressReference, setAddressReference] = useState("");
  const [province, setProvince] = useState("");
  const [city, setCity] = useState("");
  const [searchingCustomers, setSearchingCustomers] = useState(false);
  const [notes, setNotes] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [searching, setSearching] = useState(false);
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [preview, setPreview] = useState<CounterSalePreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (lines.length === 0 || lines.some((line) => line.quantity < 1)) {
      setPreview(null);
      setPreviewError(null);
      setPreviewLoading(false);
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    const handle = window.setTimeout(() => {
      void ordersApi
        .previewCounterSale(
          lines.map((line) => ({
            product_id: line.productId,
            quantity: line.quantity,
          })),
        )
        .then((data) => {
          if (cancelled) return;
          setPreview(data);
          setPreviewError(null);
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          setPreview(null);
          setPreviewError(saleError(err));
        })
        .finally(() => {
          if (!cancelled) setPreviewLoading(false);
        });
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [lines]);

  const previewReady =
    preview != null &&
    preview.items.length === lines.length &&
    lines.every((line) =>
      preview.items.some(
        (item) =>
          item.product_id === line.productId && item.quantity === line.quantity,
      ),
    );

  function amountsFor(line: Line) {
    const priced = previewReady
      ? preview?.items.find((item) => item.product_id === line.productId)
      : undefined;
    const currency = preview?.currency ?? "USD";
    const unit = priced?.unit_price ?? line.unitPrice;
    if (!unit) return null;
    const lineTotal =
      priced?.line_total ?? String(Number(unit) * line.quantity);
    return { unit, lineTotal, currency };
  }

  const buyerLabel = customer
    ? `${customer.first_name} ${customer.last_name}`.trim()
    : walkInName.trim() || "Consumidor final";

  async function searchCustomers() {
    const term = customerQuery.trim();
    if (!term) return;
    setSearchingCustomers(true);
    setError(null);
    try {
      const data = await adminCustomersApi.list({
        q: term,
        page: 1,
        page_size: 8,
        is_active: true,
      });
      setCustomerResults(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo buscar clientes");
      setCustomerResults([]);
    } finally {
      setSearchingCustomers(false);
    }
  }

  async function searchProducts() {
    const term = query.trim();
    if (!term) return;
    setSearching(true);
    setError(null);
    try {
      const data = await catalogApi.listProducts(
        { search: term, page: 1, page_size: 8, is_active: true },
        true,
      );
      setResults(data.items);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo buscar");
      setResults([]);
    } finally {
      setSearching(false);
    }
  }

  function addProduct(product: Product) {
    setLines((current) => {
      const existing = current.find((line) => line.productId === product.id);
      if (existing) {
        return current.map((line) =>
          line.productId === product.id
            ? { ...line, quantity: line.quantity + 1 }
            : line,
        );
      }
      return [
        ...current,
        {
          productId: product.id,
          name: product.name,
          sku: product.sku,
          quantity: 1,
          unitPrice: product.price?.amount ?? null,
        },
      ];
    });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (lines.length === 0) {
      setError("Agrega al menos un producto.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const order = await ordersApi.createCounterSale({
        customer_id: customer?.id ?? null,
        customer_name: customer ? null : walkInName.trim() || null,
        customer_phone: customer ? null : walkInPhone.trim() || null,
        customer_notes: notes.trim() || null,
        buyer_id_type: (buyerIdType || null) as "CEDULA" | "RUC" | "PASAPORTE" | null,
        buyer_id_number: buyerIdNumber.trim() || null,
        address_line: addressLine.trim() || null,
        address_reference: addressReference.trim() || null,
        city: city || null,
        province: province || null,
        country: addressLine.trim() ? "Ecuador" : null,
        items: lines.map((line) => ({
          product_id: line.productId,
          quantity: line.quantity,
        })),
      });
      router.push(`/admin/orders/${order.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo registrar la venta");
      setSaving(false);
    }
  }

  return (
    <AdminShell title="Nueva venta">
      <div className="mb-4">
        <Link href="/admin/orders" className="text-sm text-cyan underline">
          Volver a pedidos
        </Link>
      </div>

      <p className="mb-6 max-w-2xl text-sm text-secondary">
        Venta en tienda física. No hace falta crear una cuenta: agrega los
        productos y registra la venta. Si la persona ya está en Clientes,
        puedes asignarle el pedido. Queda pagado en efectivo y el stock se
        descuenta de inmediato.
      </p>

      {error ? (
        <p
          className="mb-4 rounded-md border border-error/30 bg-error/5 px-4 py-3 text-sm text-error"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      <form onSubmit={(event) => void save(event)}>
        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-6">
        <section className="gema-panel space-y-4 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-display text-lg font-semibold">Cliente</h2>
            <Link href="/admin/customers" className="text-sm text-cyan underline">
              Cuentas en Clientes
            </Link>
          </div>
          <p className="text-sm text-secondary">
            Opcional. Sin cliente, la venta queda solo en este pedido.
          </p>
          {customer ? (
            <p className="text-sm">
              <span className="font-medium">
                {customer.first_name} {customer.last_name}
              </span>
              <span className="ml-2 text-secondary">{customer.email}</span>
              <button
                type="button"
                className="btn-ghost btn-sm ml-2"
                onClick={() => setCustomer(null)}
              >
                Cambiar
              </button>
            </p>
          ) : (
            <>
              <div className="flex gap-2">
                <FormField label="Buscar cliente" className="min-w-0 flex-1">
                  <Input
                    value={customerQuery}
                    onChange={(event) => setCustomerQuery(event.target.value)}
                    placeholder="Nombre o correo"
                  />
                </FormField>
                <button
                  type="button"
                  className="btn-secondary self-end"
                  disabled={searchingCustomers}
                  onClick={() => void searchCustomers()}
                >
                  {searchingCustomers ? "Buscando…" : "Buscar"}
                </button>
              </div>
              {customerResults.length > 0 ? (
                <ul className="divide-y divide-border rounded-md border border-border">
                  {customerResults.map((item) => (
                    <li
                      key={item.id}
                      className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                    >
                      <span>
                        {item.first_name} {item.last_name}
                        <span className="ml-2 text-secondary">{item.email}</span>
                      </span>
                      <button
                        type="button"
                        className="btn-secondary btn-sm"
                        onClick={() => {
                          setCustomer(item);
                          setBuyerIdType(item.tax_id_type ?? "");
                          setBuyerIdNumber(item.tax_id ?? "");
                          setAddressLine(item.address_line ?? "");
                          setAddressReference(item.address_reference ?? "");
                          setProvince(item.province ?? "");
                          setCity(item.city ?? "");
                        }}
                      >
                        Elegir
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              <div className="grid gap-4 sm:grid-cols-2">
                <FormField label="Nombre en el pedido">
                  <Input
                    value={walkInName}
                    onChange={(event) => setWalkInName(event.target.value)}
                    placeholder="Opcional"
                  />
                </FormField>
                <FormField label="Teléfono">
                  <Input
                    value={walkInPhone}
                    onChange={(event) => setWalkInPhone(event.target.value)}
                    placeholder={buyerIdType ? "Obligatorio para facturar" : "Opcional"}
                    required={Boolean(buyerIdType)}
                  />
                </FormField>
              </div>
            </>
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Nota de venta">
              <Select
                value={buyerIdType}
                onChange={(event) => setBuyerIdType(event.target.value)}
              >
                <option value="">Consumidor final</option>
                <option value="CEDULA">Cédula</option>
                <option value="RUC">RUC</option>
                <option value="PASAPORTE">Pasaporte</option>
              </Select>
            </FormField>
            <FormField
              label="Número"
              hint="Cédula, RUC o pasaporte. Con identificación hace falta la dirección para facturar."
            >
              <Input
                value={buyerIdNumber}
                onChange={(event) => setBuyerIdNumber(event.target.value)}
                disabled={!buyerIdType}
                required={Boolean(buyerIdType)}
                inputMode={buyerIdType === "PASAPORTE" ? "text" : "numeric"}
              />
            </FormField>
            <FormField label="Provincia">
              <Select
                value={province}
                required={Boolean(buyerIdType)}
                onChange={(event) => {
                  setProvince(event.target.value);
                  setCity("");
                }}
              >
                <option value="">Seleccionar…</option>
                {ECUADOR_PROVINCES.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Ciudad">
              <Select
                value={city}
                required={Boolean(buyerIdType)}
                disabled={!province}
                onChange={(event) => setCity(event.target.value)}
              >
                <option value="">
                  {province ? "Seleccionar…" : "Elige provincia primero"}
                </option>
                {citiesForProvince(province).map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label="Dirección" className="sm:col-span-2">
              <Input
                value={addressLine}
                required={Boolean(buyerIdType)}
                onChange={(event) => setAddressLine(event.target.value)}
              />
            </FormField>
            <FormField label="Referencia" className="sm:col-span-2">
              <Input
                value={addressReference}
                onChange={(event) => setAddressReference(event.target.value)}
                placeholder="Opcional"
              />
            </FormField>
          </div>
          <FormField label="Notas">
            <Input
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </FormField>
        </section>

        <section className="gema-panel space-y-4 p-5">
          <h2 className="font-display text-lg font-semibold">Productos</h2>
          <div className="flex gap-2">
            <FormField label="Buscar" className="min-w-0 flex-1">
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Nombre o SKU"
              />
            </FormField>
            <button
              type="button"
              className="btn-secondary self-end"
              disabled={searching}
              onClick={() => void searchProducts()}
            >
              {searching ? "Buscando…" : "Buscar"}
            </button>
          </div>

          {results.length > 0 ? (
            <ul className="divide-y divide-border rounded-md border border-border">
              {results.map((product) => (
                <li
                  key={product.id}
                  className="flex items-center justify-between gap-3 px-3 py-2 text-sm"
                >
                  <span>
                    <span className="font-medium">{product.name}</span>
                    <span className="ml-2 text-secondary">{product.sku}</span>
                    {product.price ? (
                      <span className="ml-2">
                        {formatPrice(product.price) ?? product.price.amount}
                      </span>
                    ) : null}
                  </span>
                  <button
                    type="button"
                    className="btn-secondary btn-sm"
                    onClick={() => addProduct(product)}
                  >
                    Agregar
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          {lines.length === 0 ? (
            <p className="text-sm text-secondary">Todavía no hay productos en la venta.</p>
          ) : (
            <ul className="space-y-2">
              {lines.map((line) => {
                const amounts = amountsFor(line);
                return (
                <li
                  key={line.productId}
                  className="flex flex-wrap items-center gap-3 rounded-md border border-border px-3 py-2 text-sm"
                >
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{line.name}</span>
                    <span className="ml-2 text-secondary">{line.sku}</span>
                    {amounts ? (
                      <span className="mt-1 block text-secondary">
                        {money(amounts.unit, amounts.currency)}
                        {" · "}
                        {money(amounts.lineTotal, amounts.currency)}
                      </span>
                    ) : null}
                  </span>
                  <label className="flex items-center gap-2">
                    Cantidad
                    <Input
                      type="number"
                      min={1}
                      max={999}
                      value={line.quantity}
                      className="w-20"
                      onChange={(event) => {
                        const quantity = Number(event.target.value);
                        setLines((current) =>
                          current.map((item) =>
                            item.productId === line.productId
                              ? { ...item, quantity: Number.isFinite(quantity) ? quantity : 1 }
                              : item,
                          ),
                        );
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn-ghost btn-sm"
                    onClick={() =>
                      setLines((current) =>
                        current.filter((item) => item.productId !== line.productId),
                      )
                    }
                  >
                    Quitar
                  </button>
                </li>
                );
              })}
            </ul>
          )}
        </section>
        </div>

        <aside className="gema-panel sticky top-20 space-y-4 p-5">
          <div>
            <h2 className="font-display text-lg font-semibold">Venta</h2>
            <p className="text-sm text-secondary">{buyerLabel} · Efectivo</p>
          </div>

          {lines.length === 0 ? (
            <p className="text-sm text-secondary">
              Agrega productos para ver subtotales y total.
            </p>
          ) : (
            <>
              <ul className="divide-y divide-border">
                {lines.map((line) => {
                  const amounts = amountsFor(line);
                  return (
                    <li
                      key={line.productId}
                      className="flex justify-between gap-3 py-2 text-sm"
                    >
                      <div className="min-w-0">
                        <p className="truncate font-medium">{line.name}</p>
                        <p className="text-secondary">
                          {line.quantity} ×{" "}
                          {amounts ? money(amounts.unit, amounts.currency) : "—"}
                        </p>
                      </div>
                      <p className="shrink-0 font-medium">
                        {amounts ? money(amounts.lineTotal, amounts.currency) : "—"}
                      </p>
                    </li>
                  );
                })}
              </ul>
              <dl className="space-y-2 border-t border-border pt-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-secondary">Subtotal</dt>
                  <dd>
                    {previewReady && preview
                      ? money(preview.subtotal, preview.currency)
                      : "…"}
                  </dd>
                </div>
                {previewReady && preview && Number(preview.discount_total) > 0 ? (
                  <div className="flex justify-between gap-4">
                    <dt className="text-secondary">Descuento</dt>
                    <dd>-{money(preview.discount_total, preview.currency)}</dd>
                  </div>
                ) : null}
                <div className="flex justify-between gap-4">
                  <dt className="text-secondary">IVA</dt>
                  <dd>
                    {previewReady && preview
                      ? money(preview.tax_total, preview.currency)
                      : "…"}
                  </dd>
                </div>
                <div className="flex justify-between gap-4 border-t border-border pt-3 text-base font-semibold">
                  <dt>Total</dt>
                  <dd>
                    {previewReady && preview
                      ? money(preview.total, preview.currency)
                      : "…"}
                  </dd>
                </div>
              </dl>
              {previewLoading ? (
                <p className="text-xs text-secondary">Calculando…</p>
              ) : null}
              {previewError ? (
                <p className="text-sm text-error" role="alert">
                  {previewError}
                </p>
              ) : null}
            </>
          )}

          <button
            type="submit"
            className="btn-primary w-full"
            disabled={saving || lines.length === 0}
          >
            {saving ? "Registrando…" : "Registrar venta"}
          </button>
        </aside>
        </div>
      </form>
    </AdminShell>
  );
}
