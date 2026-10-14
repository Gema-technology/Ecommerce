import { ApiError } from "@/lib/auth-api";

export type CartProductPrice = {
  amount: string;
  currency: string;
  price_type?: string | null;
};

export type CartProduct = {
  id: string;
  name: string;
  slug: string;
  sku: string;
  image: string | null;
  price: CartProductPrice | null;
  is_active: boolean;
  availability: "IN_STOCK" | "LOW_STOCK" | "OUT_OF_STOCK" | "UNKNOWN";
};

export type CartItem = {
  id: string;
  product: CartProduct;
  quantity: number;
  unit_price?: string | null;
  unit_discount?: string;
  line_discount?: string;
  line_total: string | null;
  quoted_unit_price?: string | null;
  price_changed?: boolean;
  available: boolean;
};

export type Cart = {
  id: string;
  status: string;
  items: CartItem[];
  subtotal: string;
  discount_total?: string;
  currency: string;
  item_count: number;
  has_price_changes?: boolean;
};

async function parseError(response: Response): Promise<{
  message: string;
  code?: string;
  details?: unknown;
}> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    const detail = data.detail;
    if (typeof detail === "string") return { message: detail };
    if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      const obj = detail as Record<string, unknown>;
      if (typeof obj.code === "string") {
        return {
          message:
            typeof obj.message === "string" ? obj.message : "Error en la solicitud",
          code: obj.code,
          details: obj,
        };
      }
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return null;
        })
        .filter(Boolean);
      if (messages.length) return { message: messages.join("; ") };
    }
    return { message: "Error en la solicitud" };
  } catch {
    return { message: "Error en la solicitud" };
  }
}

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_ORIGIN?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  }
  return "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${apiBase()}${path}`;
  const method = (init?.method ?? "GET").toUpperCase();
  const hasBody = init?.body != null && init.body !== "";
  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      credentials: "include",
      headers: {
        ...(hasBody || method === "POST" || method === "PATCH" || method === "PUT"
          ? { "Content-Type": "application/json" }
          : {}),
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(503, "API no disponible");
  }
  if (!response.ok) {
    const parsed = await parseError(response);
    throw new ApiError(response.status, parsed.message, {
      code: parsed.code,
      details: parsed.details,
    });
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const cartApi = {
  get() {
    return request<Cart>("/api/v1/cart");
  },
  addItem(productId: string, quantity = 1) {
    return request<Cart>("/api/v1/cart/items", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity }),
    });
  },
  updateItem(itemId: string, quantity: number) {
    return request<Cart>(`/api/v1/cart/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ quantity }),
    });
  },
  removeItem(itemId: string) {
    return request<Cart>(`/api/v1/cart/items/${itemId}`, {
      method: "DELETE",
    });
  },
  clear() {
    return request<Cart>("/api/v1/cart", { method: "DELETE" });
  },
  syncPrices() {
    return request<Cart>("/api/v1/cart/sync-prices", { method: "POST" });
  },
};
