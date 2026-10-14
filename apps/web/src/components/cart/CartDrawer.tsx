"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { useCart } from "@/components/cart/CartProvider";
import { Drawer } from "@/components/ui/drawer";
import { useToast } from "@/components/ui/toast";
import { AppLoading } from "@/components/shared/AppLoading";
import { ApiError } from "@/lib/auth-api";
import { cartApi } from "@/lib/cart-api";
import { formatPrice } from "@/lib/catalog-types";

function money(amount: string | null | undefined, currency = "USD") {
  if (amount == null) return "—";
  return (
    formatPrice({ amount, currency, price_type: "RETAIL" }) ??
    `${currency} ${amount}`
  );
}

export function CartDrawer({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { user, loading: authLoading } = useAuth();
  const { cart, setCart } = useCart();
  const toast = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const items = cart?.items ?? [];

  async function updateQty(itemId: string, quantity: number) {
    if (quantity < 1) return;
    setBusyId(itemId);
    setError(null);
    try {
      const data = await cartApi.updateItem(itemId, quantity);
      setCart(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar");
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
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Drawer
      open={open}
      title="Tu carrito"
      onClose={onClose}
      side="right"
      fill
    >
      {/* Fill drawer body: scrollable lines + fixed actions (no sticky overlap). */}
      <div className="-m-4 flex min-h-0 flex-1 flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
          {authLoading ? (
            <AppLoading compact label="Cargando" hideHint className="!py-8" />
          ) : null}

          {!authLoading && !user ? (
            <div className="py-8 text-center">
              <p className="text-sm text-secondary">
                Inicia sesión para ver tu carrito.
              </p>
              <Link
                href="/login"
                className="btn-primary mt-4 inline-flex"
                onClick={onClose}
              >
                Iniciar sesión
              </Link>
            </div>
          ) : null}

          {error ? (
            <p className="mb-3 text-sm text-error" role="alert">
              {error}
            </p>
          ) : null}

          {user && cart && items.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-secondary">Tu carrito está vacío.</p>
              <Link
                href="/products"
                className="btn-primary mt-4 inline-flex"
                onClick={onClose}
              >
                Ver productos
              </Link>
            </div>
          ) : null}

          {user && cart && items.length > 0 ? (
            <ul className="space-y-4">
              {items.map((item) => {
                const unavailable = !item.available || !item.product.is_active;
                const busy = busyId === item.id;
                return (
                  <li
                    key={item.id}
                    className="gema-card-media flex gap-3 border border-border p-3"
                  >
                    {item.product.image ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={item.product.image}
                        alt=""
                        className="h-16 w-16 shrink-0 border border-border bg-surface object-contain"
                      />
                    ) : (
                      <div className="gema-card-media flex h-16 w-16 shrink-0 items-center justify-center text-[10px] text-muted">
                        —
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <Link
                        href={`/products/${item.product.slug}`}
                        className="line-clamp-2 text-sm font-medium transition hover:text-foreground"
                        onClick={onClose}
                      >
                        {item.product.name}
                      </Link>
                      <p className="mt-1 font-mono text-sm text-secondary">
                        {unavailable
                          ? "No disponible"
                          : money(item.line_total, cart.currency)}
                      </p>
                      <div className="relative z-10 mt-2 flex flex-wrap items-center gap-1">
                        <button
                          type="button"
                          className="btn-ghost btn-icon btn-sm"
                          aria-label="Disminuir cantidad"
                          disabled={busy || item.quantity <= 1 || unavailable}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            void updateQty(item.id, item.quantity - 1);
                          }}
                        >
                          −
                        </button>
                        <span
                          className="min-w-6 text-center font-mono text-sm tabular-nums"
                          aria-live="polite"
                        >
                          {item.quantity}
                        </span>
                        <button
                          type="button"
                          className="btn-ghost btn-icon btn-sm"
                          aria-label="Aumentar cantidad"
                          disabled={busy || unavailable}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            void updateQty(item.id, item.quantity + 1);
                          }}
                        >
                          +
                        </button>
                        <button
                          type="button"
                          className="btn-ghost btn-sm ml-auto"
                          disabled={busy}
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            void removeItem(item.id);
                          }}
                        >
                          Eliminar
                        </button>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>

        {user && cart && items.length > 0 ? (
          <div className="shrink-0 border-t border-border bg-surface p-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <div className="mb-3 flex justify-between text-sm">
              <span className="text-secondary">Subtotal</span>
              <span className="gema-price text-base">
                {money(cart.subtotal, cart.currency)}
              </span>
            </div>
            <Link
              href="/checkout"
              className="btn-primary w-full"
              onClick={onClose}
            >
              Ir a pagar
            </Link>
            <Link
              href="/cart"
              className="btn-ghost mt-2 w-full"
              onClick={onClose}
            >
              Ver carrito completo
            </Link>
          </div>
        ) : null}
      </div>
    </Drawer>
  );
}
