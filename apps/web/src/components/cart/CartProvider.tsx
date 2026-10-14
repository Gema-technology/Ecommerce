"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { cartApi, type Cart } from "@/lib/cart-api";

type CartContextValue = {
  cart: Cart | null;
  itemCount: number;
  loading: boolean;
  refresh: () => Promise<Cart | null>;
  setCart: (cart: Cart | null) => void;
};

const CartContext = createContext<CartContextValue | undefined>(undefined);

export function CartProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth();
  const [cart, setCart] = useState<Cart | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!user) {
      setCart(null);
      return null;
    }
    setLoading(true);
    try {
      const data = await cartApi.get();
      setCart(data);
      return data;
    } catch {
      setCart(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    void (async () => {
      if (!user) {
        if (!cancelled) setCart(null);
        return;
      }
      setLoading(true);
      try {
        const data = await cartApi.get();
        if (!cancelled) setCart(data);
      } catch {
        if (!cancelled) setCart(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, authLoading]);

  const value = useMemo(
    () => ({
      cart,
      itemCount: cart?.item_count ?? 0,
      loading,
      refresh,
      setCart,
    }),
    [cart, loading, refresh],
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) {
    throw new Error("useCart must be used within CartProvider");
  }
  return ctx;
}
