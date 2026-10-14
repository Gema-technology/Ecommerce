"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { useCart } from "@/components/cart/CartProvider";
import { StoreShell } from "@/components/layout/StoreShell";
import { AppLoading } from "@/components/shared/AppLoading";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/auth-api";
import { cartApi } from "@/lib/cart-api";
import { formatPrice } from "@/lib/catalog-types";

function money(amount: string | null | undefined, currency = "USD") {
  if (amount == null) return "Consultar precio";
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export default function CartPage() {
  const { user, loading: authLoading } = useAuth();
  const { cart, setCart, loading: cartLoading, refresh } = useCart();
  const toast = useToast();
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function updateQty(itemId: string, quantity: number) {
    if (quantity < 1) return;
    setBusyId(itemId);
    setError(null);
    try {
      const data = await cartApi.updateItem(itemId, quantity);
      setCart(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar");
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function removeItem(itemId: string) {
    setBusyId(itemId);
    setError(null);
    try {
      const data = await cartApi.removeItem(itemId);
      setCart(data);
      toast.success("Producto eliminado del carrito.");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo eliminar";
      setError(msg);
      toast.error(msg);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  async function clearCart() {
    setBusyId("clear");
    setError(null);
    try {
      const data = await cartApi.clear();
      setCart(data);
      toast.success("Carrito vaciado.");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo vaciar";
      setError(msg);
      toast.error(msg);
      await refresh();
    } finally {
      setBusyId(null);
    }
  }

  const loading = authLoading || (Boolean(user) && cartLoading && !cart);

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-10">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-navy">
          Carrito
        </h1>

        {loading ? (
          <AppLoading compact label="Cargando carrito" hideHint className="!py-16" />
        ) : null}

        {!loading && !user ? (
          <div className="gema-panel mt-8 px-6 py-12 text-center">
            <p className="text-lg font-medium">Inicia sesión para ver tu carrito</p>
            <Link href="/login" className="btn-primary mt-6 inline-flex">
              Iniciar sesión
            </Link>
          </div>
        ) : null}

        {error ? (
          <p className="mt-4 text-sm font-medium text-error" role="alert">
            {error}
          </p>
        ) : null}

        {user && cart && cart.items.length === 0 ? (
          <div className="gema-panel mt-8 px-6 py-12 text-center">
            <p className="text-lg font-medium">Tu carrito está vacío.</p>
            <Link href="/products" className="btn-primary mt-6 inline-flex">
              Ver productos
            </Link>
          </div>
        ) : null}

        {user && cart && cart.items.length > 0 ? (
          <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_18rem]">
            <div className="space-y-4">
              {cart.items.map((item) => {
                const unavailable = !item.available || !item.product.is_active;
                const busy = busyId === item.id;
                return (
                  <article
                    key={item.id}
                    className="gema-card flex flex-col gap-4 p-4 sm:flex-row"
                  >
                    {item.product.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.product.image}
                        alt={item.product.name}
                        className="h-28 w-28 shrink-0 rounded-[var(--radius-lg)] bg-surface-elevated object-contain"
                      />
                    ) : (
                      <div className="flex h-28 w-28 shrink-0 items-center justify-center rounded-[var(--radius-lg)] bg-surface-elevated text-xs text-muted">
                        Sin imagen
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/products/${item.product.slug}`}
                        className="line-clamp-2 font-medium text-foreground hover:underline"
                      >
                        {item.product.name}
                      </Link>
                      <p className="mt-1 text-sm text-secondary">
                        SKU {item.product.sku}
                      </p>
                      {unavailable ? (
                        <p className="mt-2 text-sm font-medium text-error">
                          No disponible actualmente
                        </p>
                      ) : (
                        <p className="mt-2 text-sm text-foreground">
                          {money(
                            item.product.price?.amount,
                            item.product.price?.currency ?? cart.currency,
                          )}{" "}
                          c/u
                        </p>
                      )}
                      <div className="relative z-10 mt-4 flex flex-wrap items-center gap-3">
                        <div className="inline-flex items-center overflow-hidden rounded-[var(--radius-lg)] border border-border bg-surface">
                          <button
                            type="button"
                            className="btn-ghost btn-icon btn-sm !rounded-none"
                            aria-label="Disminuir cantidad"
                            disabled={busy || item.quantity <= 1 || unavailable}
                            onClick={(e) => {
                              e.preventDefault();
                              void updateQty(item.id, item.quantity - 1);
                            }}
                          >
                            −
                          </button>
                          <span
                            className="min-w-10 text-center text-sm tabular-nums"
                            aria-live="polite"
                            aria-label={`Cantidad ${item.quantity}`}
                          >
                            {item.quantity}
                          </span>
                          <button
                            type="button"
                            className="btn-ghost btn-icon btn-sm !rounded-none"
                            aria-label="Aumentar cantidad"
                            disabled={busy || unavailable}
                            onClick={(e) => {
                              e.preventDefault();
                              void updateQty(item.id, item.quantity + 1);
                            }}
                          >
                            +
                          </button>
                        </div>
                        <button
                          type="button"
                          className="btn-ghost btn-sm"
                          disabled={busy}
                          onClick={(e) => {
                            e.preventDefault();
                            void removeItem(item.id);
                          }}
                        >
                          Eliminar
                        </button>
                      </div>
                    </div>
                    <div className="text-right sm:w-28">
                      <p className="text-sm text-secondary">Subtotal</p>
                      <p className="font-semibold">
                        {unavailable
                          ? "—"
                          : money(item.line_total, cart.currency)}
                      </p>
                    </div>
                  </article>
                );
              })}
              <button
                type="button"
                className="btn-ghost"
                disabled={busyId === "clear"}
                onClick={() => void clearCart()}
              >
                Vaciar carrito
              </button>
            </div>

            <aside className="gema-panel h-fit p-5">
              <h2 className="font-display font-semibold">Resumen</h2>
              <div className="mt-4 flex items-center justify-between text-sm">
                <span>Subtotal</span>
                <span className="font-semibold">
                  {money(cart.subtotal, cart.currency)}
                </span>
              </div>
              <p className="mt-2 text-xs text-muted">
                Envío e IVA se confirman en el checkout según la configuración
                del comercio.
              </p>
              <Link
                href="/checkout"
                className="btn-primary mt-6 inline-flex w-full justify-center"
              >
                Continuar compra
              </Link>
              <Link
                href="/products"
                className="btn-ghost mt-3 inline-flex w-full justify-center"
              >
                Seguir comprando
              </Link>
            </aside>
          </div>
        ) : null}
      </main>
    </StoreShell>
  );
}
