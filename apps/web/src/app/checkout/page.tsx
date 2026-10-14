"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { CheckoutSummary } from "@/components/checkout/CheckoutSummary";
import { useAuth } from "@/components/auth/AuthProvider";
import { useCart } from "@/components/cart/CartProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { Select } from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import {
  ApiError,
  type PriceChangedDetail,
  type PriceChangedItem,
} from "@/lib/auth-api";
import { cartApi, type Cart } from "@/lib/cart-api";
import { formatPrice } from "@/lib/catalog-types";
import {
  CHECKOUT_STEPS,
  citiesForProvince,
  ECUADOR_PROVINCES,
} from "@/lib/checkout-types";
import { cn } from "@/lib/cn";
import {
  ordersApi,
  type BuyerIdType,
  type CheckoutPreview,
  type ShippingAddress,
} from "@/lib/orders-api";

function money(amount: string, currency = "USD") {
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

function asPriceChanged(err: ApiError): PriceChangedDetail | null {
  if (err.code !== "PRICE_CHANGED" || !err.details || typeof err.details !== "object") {
    return null;
  }
  const detail = err.details as PriceChangedDetail;
  if (!Array.isArray(detail.items)) return null;
  return detail;
}

const emptyAddress: ShippingAddress = {
  recipient_name: "",
  phone: "",
  address_line: "",
  reference: "",
  city: "",
  province: "",
  country: "Ecuador",
  postal_code: "",
};

function fieldError(message: string) {
  return (
    <p className="mt-1 text-xs text-error" role="alert">
      {message}
    </p>
  );
}

export default function CheckoutPage() {
  const { user, loading: authLoading } = useAuth();
  const { setCart, refresh } = useCart();
  const toast = useToast();
  const router = useRouter();
  const [cart, setLocalCart] = useState<Cart | null>(null);
  const [cartLoading, setCartLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [priceChanges, setPriceChanges] = useState<PriceChangedItem[] | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [address, setAddress] = useState<ShippingAddress>(emptyAddress);
  const [notes, setNotes] = useState("");
  const [buyerIdType, setBuyerIdType] =
    useState<BuyerIdType>("CONSUMIDOR_FINAL");
  const [buyerIdNumber, setBuyerIdNumber] = useState("");
  const [step, setStep] = useState(0);
  const [preview, setPreview] = useState<CheckoutPreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    void (async () => {
      if (!user) {
        setCartLoading(false);
        return;
      }
      try {
        const data = await cartApi.get();
        if (!cancelled) setLocalCart(data);
        if (!cancelled) {
          setAddress((prev) => ({
            ...prev,
            recipient_name:
              prev.recipient_name ||
              `${user.first_name} ${user.last_name ?? ""}`.trim(),
            phone: prev.phone || user.phone || "",
          }));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "No se pudo cargar el carrito",
          );
        }
      } finally {
        if (!cancelled) setCartLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading]);

  const loadPreview = useCallback(
    async (shipping?: ShippingAddress | null) => {
      if (!user || !cart?.items.length) return;
      setPreviewLoading(true);
      try {
        const data = await ordersApi.previewCheckout({
          shipping_address: shipping ?? null,
        });
        setPreview(data);
      } catch (err) {
        if (err instanceof ApiError) {
          const changed = asPriceChanged(err);
          if (changed) setPriceChanges(changed.items);
        }
      } finally {
        setPreviewLoading(false);
      }
    },
    [user, cart?.items.length],
  );

  useEffect(() => {
    if (step >= 1 && address.province && address.city) {
      void loadPreview(address);
    }
    // Preview only when province/city change — not on every address keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- intentional partial address deps
  }, [step, address.province, address.city, loadPreview]);

  function updateAddress<K extends keyof ShippingAddress>(
    key: K,
    value: ShippingAddress[K],
  ) {
    setAddress((prev) => {
      if (key === "province") {
        const nextProvince = String(value);
        const cities = citiesForProvince(nextProvince);
        const cityStillValid = cities.includes(prev.city);
        return {
          ...prev,
          province: nextProvince,
          city: cityStillValid ? prev.city : "",
        };
      }
      return { ...prev, [key]: value };
    });
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      if (key === "province") delete next.city;
      return next;
    });
  }

  function validateStep(current: number): boolean {
    const errors: Record<string, string> = {};
    if (current === 0) {
      if (!address.recipient_name.trim()) {
        errors.recipient_name = "Ingresa tu nombre completo.";
      }
      const phoneDigits = address.phone.replace(/\D/g, "");
      if (!address.phone.trim() || phoneDigits.length < 9) {
        errors.phone = "Ingresa un número de teléfono válido.";
      }
      if (
        buyerIdType !== "CONSUMIDOR_FINAL" &&
        !buyerIdNumber.trim()
      ) {
        errors.buyer_id_number = "Ingresa tu cédula, RUC o pasaporte.";
      }
    }
    if (current === 1) {
      if (!address.address_line.trim()) {
        errors.address_line = "Ingresa la dirección de entrega.";
      }
      if (!address.province.trim()) errors.province = "Selecciona la provincia.";
      if (!address.city.trim()) {
        errors.city = "Selecciona la ciudad.";
      } else if (
        !citiesForProvince(address.province).includes(address.city.trim())
      ) {
        errors.city = "Selecciona una ciudad de la lista.";
      }
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function goNext() {
    setError(null);
    if (!validateStep(step)) return;
    setStep((s) => Math.min(CHECKOUT_STEPS.length - 2, s + 1));
  }

  async function confirm(event: FormEvent) {
    event.preventDefault();
    if (step < CHECKOUT_STEPS.length - 2) {
      goNext();
      return;
    }
    if (!validateStep(0) || !validateStep(1)) return;

    setSubmitting(true);
    setError(null);
    setPriceChanges(null);
    try {
      const result = await ordersApi.checkout({
        shipping_address: {
          ...address,
          reference: address.reference || null,
          postal_code: address.postal_code || null,
        },
        customer_notes: notes.trim() || null,
        buyer_id_type: buyerIdType,
        buyer_id_number:
          buyerIdType === "CONSUMIDOR_FINAL"
            ? null
            : buyerIdNumber.trim() || null,
      });
      setCart(null);
      await refresh();
      toast.success("Pedido creado. Continúa con el pago.");
      router.push(
        `/orders/${encodeURIComponent(result.order_number)}/payment`,
      );
    } catch (err) {
      if (err instanceof ApiError) {
        const changed = asPriceChanged(err);
        if (changed) {
          setPriceChanges(changed.items);
          setError(null);
          toast.warning("Algunos precios cambiaron. Revísalos antes de continuar.");
        } else if (err.status === 422) {
          const msg = "Revisa los datos del formulario e intenta nuevamente.";
          setError(msg);
          toast.error(msg);
        } else if (err.status === 409) {
          const msg =
            err.message.includes("stock") || err.message.includes("quantity")
              ? "Uno o más productos no tienen stock suficiente."
              : err.message;
          setError(msg);
          toast.error(msg);
        } else {
          setError(err.message);
          toast.error(err.message);
        }
      } else {
        const msg = "No se pudo completar la compra. Verifica tu conexión.";
        setError(msg);
        toast.error(msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function updateCartPrices() {
    setSyncing(true);
    setError(null);
    try {
      const data = await cartApi.syncPrices();
      setLocalCart(data);
      setCart(data);
      setPriceChanges(null);
      await loadPreview(address.province ? address : null);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo actualizar el carrito",
      );
    } finally {
      setSyncing(false);
    }
  }

  const unavailable =
    cart?.items.some((i) => !i.available || !i.product.is_active) ?? false;
  const blockedByPriceChange = Boolean(priceChanges?.length);
  const reviewStep = CHECKOUT_STEPS.length - 2;

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-12 sm:py-16">
        <header className="max-w-xl">
          <p className="text-sm font-medium uppercase tracking-[0.14em] text-primary">
            Compra segura
          </p>
          <h1 className="font-display mt-2 text-4xl font-semibold tracking-tight text-navy">
            Finalizar compra
          </h1>
          <p className="mt-3 text-base text-secondary">
            Completa tus datos, confirma el envío y revisa tu pedido antes de
            pagar.
          </p>
        </header>

        {authLoading || cartLoading ? (
          <AppLoading compact label="Cargando compra" hideHint className="!py-16" />
        ) : null}

        {!authLoading && !user ? (
          <div className="gema-panel mt-10 max-w-md px-8 py-14 text-center">
            <p className="font-display text-xl font-semibold text-navy">
              Inicia sesión para continuar
            </p>
            <Link href="/login" className="btn-primary mt-8 inline-flex">
              Iniciar sesión
            </Link>
          </div>
        ) : null}

        {error ? (
          <p className="mt-6 text-sm font-medium text-error" role="alert">
            {error}
          </p>
        ) : null}

        {priceChanges?.length ? (
          <div
            className="gema-panel mt-8 max-w-2xl border-warning/40 p-6"
            role="alert"
          >
            <p className="font-display text-base font-semibold">Precio actualizado</p>
            <p className="mt-1 text-sm text-secondary">
              El precio de uno o más productos cambió. Actualiza tu carrito para
              continuar.
            </p>
            <ul className="mt-4 space-y-3">
              {priceChanges.map((item) => (
                <li
                  key={item.product_id}
                  className="rounded-[var(--radius-md)] bg-surface-image px-3 py-3 text-sm"
                >
                  <p className="font-medium">{item.product_name}</p>
                  <div className="mt-2 flex gap-6 text-secondary">
                    <span>
                      Antes{" "}
                      <span className="line-through">
                        {money(item.previous_unit_price, item.currency)}
                      </span>
                    </span>
                    <span>
                      Ahora{" "}
                      <span className="font-semibold text-foreground">
                        {money(item.current_unit_price, item.currency)}
                      </span>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
            <button
              type="button"
              className="btn-primary mt-5"
              disabled={syncing}
              onClick={() => void updateCartPrices()}
            >
              {syncing ? "Actualizando…" : "Actualizar carrito"}
            </button>
          </div>
        ) : null}

        {user && cart && cart.items.length === 0 ? (
          <div className="gema-panel mt-10 max-w-md px-8 py-14 text-center">
            <p className="font-display text-xl font-semibold text-navy">
              Tu carrito está vacío
            </p>
            <Link href="/products" className="btn-primary mt-8 inline-flex">
              Ver productos
            </Link>
          </div>
        ) : null}

        {user && cart && cart.items.length > 0 ? (
          <>
            <nav
              className="gema-steps mt-10 max-w-3xl"
              aria-label="Pasos de la compra"
            >
              {CHECKOUT_STEPS.map((label, i) => (
                <div key={label} className="contents">
                  <div
                    className={cn(
                      "gema-step",
                      i === step && "is-active",
                      i < step && "is-done",
                    )}
                  >
                    <span className="gema-step-index">{i + 1}</span>
                    <span className="gema-step-label hidden sm:inline">{label}</span>
                  </div>
                  {i < CHECKOUT_STEPS.length - 1 ? (
                    <div
                      className={cn("gema-step-line", i < step && "bg-primary!")}
                    />
                  ) : null}
                </div>
              ))}
            </nav>

            <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_20rem] lg:gap-12">
              <form
                className="min-w-0 space-y-6"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (step < reviewStep) {
                    goNext();
                    return;
                  }
                  void confirm(e);
                }}
                noValidate
              >
                {step === 0 ? (
                  <section className="gema-panel space-y-5 p-6 sm:p-8">
                    <div>
                      <h2 className="font-display text-lg font-semibold text-navy">
                        Tus datos
                      </h2>
                      <p className="mt-1 text-sm text-secondary">
                        Usaremos esta información para contactarte sobre tu pedido.
                      </p>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="label-field sm:col-span-2">
                        Nombre completo
                        <input
                          className="input-field mt-1.5"
                          autoComplete="name"
                          value={address.recipient_name}
                          onChange={(e) =>
                            updateAddress("recipient_name", e.target.value)
                          }
                          aria-invalid={Boolean(fieldErrors.recipient_name)}
                        />
                        {fieldErrors.recipient_name
                          ? fieldError(fieldErrors.recipient_name)
                          : null}
                      </label>
                      <label className="label-field sm:col-span-2">
                        Correo
                        <input
                          className="input-field mt-1.5 bg-surface-image"
                          type="email"
                          readOnly
                          value={user.email}
                          aria-readonly
                        />
                      </label>
                      <label className="label-field sm:col-span-2">
                        Teléfono
                        <input
                          className="input-field mt-1.5"
                          type="tel"
                          inputMode="tel"
                          autoComplete="tel"
                          value={address.phone}
                          onChange={(e) => updateAddress("phone", e.target.value)}
                          aria-invalid={Boolean(fieldErrors.phone)}
                        />
                        {fieldErrors.phone ? fieldError(fieldErrors.phone) : null}
                      </label>
                      <label className="label-field">
                        Identificación (factura)
                        <select
                          className="input-field mt-1.5"
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
                        </select>
                      </label>
                      <label className="label-field">
                        Número de identificación
                        <input
                          className="input-field mt-1.5"
                          disabled={buyerIdType === "CONSUMIDOR_FINAL"}
                          value={
                            buyerIdType === "CONSUMIDOR_FINAL"
                              ? "Consumidor final"
                              : buyerIdNumber
                          }
                          onChange={(e) => setBuyerIdNumber(e.target.value)}
                          aria-invalid={Boolean(fieldErrors.buyer_id_number)}
                        />
                        {fieldErrors.buyer_id_number
                          ? fieldError(fieldErrors.buyer_id_number)
                          : null}
                      </label>
                    </div>
                  </section>
                ) : null}

                {step === 1 ? (
                  <section className="gema-panel space-y-5 p-6 sm:p-8">
                    <div>
                      <h2 className="font-display text-lg font-semibold text-navy">
                        Dirección de envío
                      </h2>
                      <p className="mt-1 text-sm text-secondary">
                        Entregamos en todo Ecuador. El costo de envío se calcula
                        automáticamente.
                      </p>
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="label-field">
                        Provincia
                        <Select
                          className="mt-1.5"
                          name="province"
                          required
                          value={address.province}
                          onChange={(e) =>
                            updateAddress("province", e.target.value)
                          }
                          aria-invalid={Boolean(fieldErrors.province)}
                        >
                          <option value="">Seleccionar…</option>
                          {ECUADOR_PROVINCES.map((p) => (
                            <option key={p} value={p}>
                              {p}
                            </option>
                          ))}
                        </Select>
                        {fieldErrors.province ? fieldError(fieldErrors.province) : null}
                      </label>
                      <label className="label-field">
                        Ciudad
                        <Select
                          className="mt-1.5"
                          name="city"
                          required
                          disabled={!address.province}
                          value={address.city}
                          onChange={(e) => updateAddress("city", e.target.value)}
                          aria-invalid={Boolean(fieldErrors.city)}
                        >
                          <option value="">
                            {address.province
                              ? "Seleccionar…"
                              : "Elige provincia primero"}
                          </option>
                          {citiesForProvince(address.province).map((city) => (
                            <option key={city} value={city}>
                              {city}
                            </option>
                          ))}
                        </Select>
                        {fieldErrors.city ? fieldError(fieldErrors.city) : null}
                      </label>
                      <label className="label-field sm:col-span-2">
                        Dirección
                        <input
                          className="input-field mt-1.5"
                          required
                          value={address.address_line}
                          onChange={(e) =>
                            updateAddress("address_line", e.target.value)
                          }
                          aria-invalid={Boolean(fieldErrors.address_line)}
                        />
                        {fieldErrors.address_line
                          ? fieldError(fieldErrors.address_line)
                          : null}
                      </label>
                      <label className="label-field sm:col-span-2">
                        Referencia
                        <input
                          className="input-field mt-1.5"
                          placeholder="Ej. casa esquinera, portón negro"
                          value={address.reference ?? ""}
                          onChange={(e) =>
                            updateAddress("reference", e.target.value)
                          }
                        />
                      </label>
                      <label className="label-field">
                        Código postal
                        <input
                          className="input-field mt-1.5"
                          value={address.postal_code ?? ""}
                          onChange={(e) =>
                            updateAddress("postal_code", e.target.value)
                          }
                        />
                      </label>
                      <label className="label-field">
                        País
                        <input
                          className="input-field mt-1.5 bg-surface-image"
                          readOnly
                          value={address.country}
                          aria-readonly
                        />
                      </label>
                      <label className="label-field sm:col-span-2">
                        Notas del pedido
                        <textarea
                          className="textarea-field mt-1.5"
                          maxLength={1000}
                          value={notes}
                          placeholder="Ej. entregar en la tarde, llamar al llegar…"
                          onChange={(e) => setNotes(e.target.value)}
                        />
                      </label>
                    </div>
                  </section>
                ) : null}

                {step === reviewStep ? (
                  <section className="gema-panel overflow-hidden">
                    <div className="border-b border-border px-6 py-5">
                      <h2 className="font-display text-lg font-semibold text-navy">
                        Revisión del pedido
                      </h2>
                      <p className="mt-1 text-sm text-secondary">
                        Confirma productos, envío y totales antes de continuar al
                        pago.
                      </p>
                    </div>
                    <ul className="divide-y divide-border">
                      {(preview?.items ?? []).map((item) => (
                        <li
                          key={item.product_id}
                          className="flex justify-between gap-4 px-6 py-4 text-sm"
                        >
                          <div className="min-w-0">
                            <p className="truncate font-medium">
                              {item.product_name}
                            </p>
                            <p className="text-secondary">
                              SKU {item.sku} · Cant. {item.quantity}
                            </p>
                          </div>
                          <p className="shrink-0 font-medium">
                            {money(item.line_total, preview?.currency)}
                          </p>
                        </li>
                      ))}
                    </ul>
                    <dl className="grid gap-3 border-t border-border px-6 py-5 text-sm sm:grid-cols-2">
                      <div className="min-w-0">
                        <dt className="text-muted">Destinatario</dt>
                        <dd className="mt-0.5 break-words font-medium">
                          {address.recipient_name}
                        </dd>
                      </div>
                      <div className="min-w-0">
                        <dt className="text-muted">Teléfono</dt>
                        <dd className="mt-0.5 break-words font-medium">
                          {address.phone}
                        </dd>
                      </div>
                      <div className="min-w-0 sm:col-span-2">
                        <dt className="text-muted">Dirección</dt>
                        <dd className="mt-0.5 break-words font-medium">
                          {address.address_line}
                          {address.reference ? ` · ${address.reference}` : ""}
                        </dd>
                        <dd className="break-words text-secondary">
                          {address.city}, {address.province}, {address.country}
                        </dd>
                      </div>
                      {notes.trim() ? (
                        <div className="min-w-0 sm:col-span-2">
                          <dt className="text-muted">Notas</dt>
                          <dd className="mt-0.5 break-words font-medium">
                            {notes}
                          </dd>
                        </div>
                      ) : null}
                    </dl>
                  </section>
                ) : null}

                <div className="flex flex-wrap items-center gap-3">
                  {step > 0 ? (
                    <button
                      type="button"
                      className="btn-outline"
                      onClick={() => setStep((s) => Math.max(0, s - 1))}
                    >
                      Atrás
                    </button>
                  ) : (
                    <Link href="/cart" className="btn-ghost">
                      Volver al carrito
                    </Link>
                  )}
                  {step < reviewStep ? (
                    <button type="submit" className="btn-primary">
                      Continuar
                    </button>
                  ) : (
                    <button
                      type="submit"
                      className="btn-primary"
                      disabled={submitting || unavailable || blockedByPriceChange}
                    >
                      {submitting ? "Creando orden…" : "Continuar al pago"}
                    </button>
                  )}
                </div>
                {unavailable ? (
                  <p className="text-sm text-error">
                    Quita los productos no disponibles antes de continuar.
                  </p>
                ) : null}
              </form>

              <div className="hidden lg:block">
                <CheckoutSummary
                  cart={cart}
                  preview={preview}
                  loadingPreview={previewLoading}
                />
              </div>
            </div>

            <div className="mt-8 lg:hidden">
              <CheckoutSummary
                cart={cart}
                preview={preview}
                loadingPreview={previewLoading}
              />
            </div>
          </>
        ) : null}
      </main>
    </StoreShell>
  );
}
