"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { FormField, Input, Select } from "@/components/ui/input";
import { adminCustomersApi, type Customer } from "@/lib/admin-customers-api";
import { ApiError } from "@/lib/auth-api";
import { catalogApi } from "@/lib/catalog-api";
import { citiesForProvince, ECUADOR_PROVINCES } from "@/lib/checkout-types";
import { formatPrice, type Product } from "@/lib/catalog-types";
import { ordersApi } from "@/lib/orders-api";

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
  const [postalCode, setPostalCode] = useState("");
  const [searchingCustomers, setSearchingCustomers] = useState(false);
  const [notes, setNotes] = useState("");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [searching, setSearching] = useState(false);
  const [lines, setLines] = useState<Line[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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
        postal_code: postalCode.trim() || null,
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

      <form onSubmit={(event) => void save(event)} className="space-y-6">
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
                          setPostalCode(item.postal_code ?? "");
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
            <FormField label="Referencia">
              <Input
                value={addressReference}
                onChange={(event) => setAddressReference(event.target.value)}
                placeholder="Opcional"
              />
            </FormField>
            <FormField label="Código postal">
              <Input
                value={postalCode}
                onChange={(event) => setPostalCode(event.target.value)}
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
              {lines.map((line) => (
                <li
                  key={line.productId}
                  className="flex flex-wrap items-center gap-3 rounded-md border border-border px-3 py-2 text-sm"
                >
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{line.name}</span>
                    <span className="ml-2 text-secondary">{line.sku}</span>
                    {line.unitPrice ? (
                      <span className="ml-2">{line.unitPrice}</span>
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
              ))}
            </ul>
          )}
        </section>

        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Registrando…" : "Registrar venta"}
        </button>
      </form>
    </AdminShell>
  );
}
