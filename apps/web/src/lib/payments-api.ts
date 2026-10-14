import { ApiError } from "@/lib/auth-api";

export type Payment = {
  id: string;
  payment_id?: string;
  order_id: string;
  order_number: string | null;
  provider: string;
  provider_payment_id: string | null;
  method: string;
  status: string;
  amount: string;
  currency: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  paid_at: string | null;
  client_action?: {
    type?: string;
    url?: string;
    payment_id?: string;
    hint?: string;
    reference?: string;
    amount?: string;
    currency?: string;
    bank?: {
      bank_name?: string;
      account_type?: string;
      account_number?: string;
      account_holder?: string;
      account_id?: string;
      extra_instructions?: string;
    };
    customer_marked_transferred?: boolean;
  } | null;
};

export type PaymentListResponse = {
  items: Payment[];
  page?: number;
  page_size?: number;
  total?: number;
  total_pages?: number;
};

async function parseError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return null;
        })
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
    return "Error en la solicitud";
  } catch {
    return "Error en la solicitud";
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
    throw new ApiError(response.status, await parseError(response));
  }
  return (await response.json()) as T;
}

export function paymentStatusLabel(status: string): string {
  switch (status) {
    case "PENDING":
      return "Pendiente";
    case "PROCESSING":
      return "Procesando";
    case "SUCCEEDED":
      return "Exitoso";
    case "FAILED":
      return "Fallido";
    case "CANCELLED":
      return "Cancelado";
    case "REFUNDED":
      return "Reembolsado";
    default:
      return status;
  }
}

export function paymentMethodLabel(method: string): string {
  switch (method) {
    case "CARD":
      return "Tarjeta";
    case "BANK_TRANSFER":
      return "Transferencia bancaria";
    case "CASH_ON_DELIVERY":
      return "Contra entrega";
    default:
      return method;
  }
}

export const paymentsApi = {
  create(orderId: string, method: string = "CARD") {
    return request<Payment>(`/api/v1/orders/${orderId}/payment`, {
      method: "POST",
      body: JSON.stringify({ method }),
    });
  },
  listForOrder(orderId: string) {
    return request<PaymentListResponse>(`/api/v1/orders/${orderId}/payments`);
  },
  get(paymentId: string) {
    return request<Payment>(`/api/v1/payments/${paymentId}`);
  },
  sync(paymentId: string) {
    return request<Payment>(`/api/v1/payments/${paymentId}/sync`, {
      method: "POST",
    });
  },
  markTransferred(paymentId: string) {
    return request<Payment>(`/api/v1/payments/${paymentId}/mark-transferred`, {
      method: "POST",
    });
  },
  adminConfirm(paymentId: string, success = true) {
    return request<Payment>(
      `/api/v1/admin/payments/${paymentId}/confirm?success=${success ? "true" : "false"}`,
      { method: "POST" },
    );
  },
  adminList(params?: {
    page?: number;
    page_size?: number;
    status?: string;
    provider?: string;
    q?: string;
  }) {
    const qs = new URLSearchParams();
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 20));
    if (params?.status) qs.set("status", params.status);
    if (params?.provider) qs.set("provider", params.provider);
    if (params?.q) qs.set("q", params.q);
    return request<PaymentListResponse>(`/api/v1/admin/payments?${qs}`);
  },
  adminGet(paymentId: string) {
    return request<Payment>(`/api/v1/admin/payments/${paymentId}`);
  },
};
