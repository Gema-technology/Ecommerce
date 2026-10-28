import { ApiError } from "@/lib/auth-api";

export type ShippingAddress = {
  recipient_name: string;
  phone: string;
  address_line: string;
  reference?: string | null;
  city: string;
  province: string;
  country: string;
  postal_code?: string | null;
};

export type BuyerIdType = "CEDULA" | "RUC" | "PASAPORTE" | "CONSUMIDOR_FINAL";

export type CheckoutRequest = {
  shipping_address: ShippingAddress;
  customer_notes?: string | null;
  buyer_id_type?: BuyerIdType | null;
  buyer_id_number?: string | null;
};

export type OrderItem = {
  id: string;
  product_id: string;
  product_name_snapshot: string;
  sku_snapshot: string;
  unit_price: string;
  quantity: number;
  line_total: string;
  line_discount?: string;
  created_at: string;
};

export type OrderReservation = {
  id: string;
  inventory_id: string;
  product_id: string | null;
  quantity: number;
  status: string;
  expires_at: string | null;
  created_at: string;
};

export type OrderStatusEvent = {
  id: string;
  from_status: string;
  to_status: string;
  actor_user_id?: string | null;
  note?: string | null;
  created_at: string;
};

export type CounterSaleItem = {
  product_id: string;
  quantity: number;
};

export type CounterSaleRequest = {
  customer_id?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  customer_notes?: string | null;
  buyer_id_type?: "CEDULA" | "RUC" | "PASAPORTE" | null;
  buyer_id_number?: string | null;
  address_line?: string | null;
  address_reference?: string | null;
  city?: string | null;
  province?: string | null;
  country?: string | null;
  postal_code?: string | null;
  items: CounterSaleItem[];
};

export type Order = {
  id: string;
  order_number: string;
  status: string;
  channel?: string;
  currency: string;
  subtotal: string;
  tax_total: string;
  shipping_total: string;
  discount_total: string;
  total: string;
  shipping_address?: ShippingAddress | null;
  customer_notes?: string | null;
  reserved_until?: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  customer_email?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  buyer_id_type?: string | null;
  buyer_id_number?: string | null;
  reservations?: OrderReservation[];
  allowed_transitions?: string[];
  status_history?: OrderStatusEvent[];
};

export type FulfillmentStatus = "PROCESSING" | "SHIPPED" | "DELIVERED";

export type OrderListResponse = {
  items: Order[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type CheckoutPreviewItem = {
  product_id: string;
  product_name: string;
  sku: string;
  quantity: number;
  unit_price: string;
  unit_discount?: string;
  line_discount?: string;
  line_total: string;
  price_type?: string | null;
};

export type CheckoutPreview = {
  currency: string;
  subtotal: string;
  tax_total: string;
  shipping_total: string;
  discount_total: string;
  total: string;
  shipping_method: string;
  tax_enabled: boolean;
  items: CheckoutPreviewItem[];
};

export type CheckoutResponse = {
  order_id: string;
  order_number: string;
  status: string;
  currency: string;
  subtotal: string;
  tax_total: string;
  shipping_total: string;
  discount_total: string;
  total: string;
  customer_email?: string | null;
  customer_name?: string | null;
  customer_phone?: string | null;
  shipping_address?: ShippingAddress | null;
  customer_notes?: string | null;
  items: {
    product_id: string;
    product_name: string;
    quantity: number;
    unit_price: string;
    line_total: string;
  }[];
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
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
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

export function orderStatusLabel(status: string): string {
  switch (status) {
    case "PENDING_PAYMENT":
      return "Pendiente de pago";
    case "PAID":
      return "Pagada";
    case "PROCESSING":
      return "En proceso";
    case "SHIPPED":
      return "Enviada";
    case "DELIVERED":
      return "Entregada";
    case "CANCELLED":
      return "Cancelada";
    default:
      return status;
  }
}

export function formatReservationExpiry(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("es-EC", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return null;
  }
}

export const ordersApi = {
  previewCheckout(payload: { shipping_address?: ShippingAddress | null } = {}) {
    return request<CheckoutPreview>("/api/v1/checkout/preview", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  checkout(payload: CheckoutRequest) {
    return request<CheckoutResponse>("/api/v1/checkout", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  cancel(orderId: string) {
    return request<Order>(`/api/v1/orders/${orderId}/cancel`, {
      method: "POST",
    });
  },
  adminCancel(orderId: string) {
    return request<Order>(`/api/v1/admin/orders/${orderId}/cancel`, {
      method: "POST",
    });
  },
  list(page = 1, pageSize = 20) {
    const qs = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    return request<OrderListResponse>(`/api/v1/orders?${qs}`);
  },
  get(orderId: string) {
    return request<Order>(`/api/v1/orders/${orderId}`);
  },
  getByNumber(orderNumber: string) {
    return request<Order>(
      `/api/v1/orders/by-number/${encodeURIComponent(orderNumber)}`,
    );
  },
  adminList(params?: { page?: number; page_size?: number; status?: string }) {
    const qs = new URLSearchParams();
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 20));
    if (params?.status) qs.set("status", params.status);
    return request<OrderListResponse>(`/api/v1/admin/orders?${qs}`);
  },
  adminGet(orderId: string) {
    return request<Order>(`/api/v1/admin/orders/${orderId}`);
  },
  adminRemoveIva(orderId: string) {
    return request<Order>(`/api/v1/admin/orders/${orderId}/remove-iva`, {
      method: "POST",
    });
  },
  createCounterSale(payload: CounterSaleRequest) {
    return request<Order>("/api/v1/admin/orders/counter-sale", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  adminUpdateStatus(
    orderId: string,
    status: FulfillmentStatus,
    note?: string | null,
  ) {
    return request<Order>(`/api/v1/admin/orders/${orderId}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status, note: note ?? null }),
    });
  },
};

export function fulfillmentActionLabel(status: string): string {
  switch (status) {
    case "PROCESSING":
      return "Marcar en preparación";
    case "SHIPPED":
      return "Marcar como enviada";
    case "DELIVERED":
      return "Marcar como entregada";
    default:
      return `Pasar a ${orderStatusLabel(status)}`;
  }
}
