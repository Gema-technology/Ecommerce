"use client";

import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { useCart } from "@/components/cart/CartProvider";
import { useToast } from "@/components/ui/toast";
import { ApiError } from "@/lib/auth-api";
import { cartApi } from "@/lib/cart-api";
import { cn } from "@/lib/cn";

export function AddToCartButton({
  productId,
  disabled = false,
}: {
  productId: string;
  disabled?: boolean;
}) {
  const { user, loading: authLoading } = useAuth();
  const { setCart } = useCart();
  const toast = useToast();
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!confirmed) return;
    const timer = window.setTimeout(() => setConfirmed(false), 1200);
    return () => window.clearTimeout(timer);
  }, [confirmed]);

  async function onAdd() {
    setError(null);
    setConfirmed(false);
    if (authLoading) return;
    if (!user) {
      router.push("/login");
      return;
    }
    setSubmitting(true);
    try {
      const cart = await cartApi.addItem(productId, 1);
      setCart(cart);
      setConfirmed(true);
      toast.success("Producto agregado al carrito.");
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "No se pudo agregar";
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="gema-panel p-5">
      <button
        type="button"
        className={cn(
          "btn-primary btn-lg w-full",
          confirmed && "btn-confirm-flash",
        )}
        disabled={disabled || submitting || authLoading}
        onClick={() => void onAdd()}
        aria-live="polite"
      >
        {confirmed ? (
          <>
            <Check className="h-4 w-4" aria-hidden />
            Agregado
          </>
        ) : submitting ? (
          "Agregando…"
        ) : (
          "Agregar al carrito"
        )}
      </button>
      {confirmed ? (
        <p className="mt-3 text-center font-mono text-xs text-success">
          Listo ·{" "}
          <button
            type="button"
            className="font-medium text-primary underline-offset-2 hover:underline"
            onClick={() => router.push("/cart")}
          >
            Ver carrito
          </button>
        </p>
      ) : (
        <p className="mt-3 text-center text-xs text-muted">
          {user
            ? "El stock se confirmará al pagar"
            : "Inicia sesión para agregar"}
        </p>
      )}
      {error ? (
        <p className="mt-2 text-center text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
