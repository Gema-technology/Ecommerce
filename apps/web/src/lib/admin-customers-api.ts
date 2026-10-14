import { ApiError } from "@/lib/auth-api";

export type Customer = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  allow_cash_on_delivery: boolean;
  roles: string[];
};

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_ORIGIN?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  }
  return "";
}

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
  } catch {
    /* non-JSON */
  }
  if (response.status === 401) return "Debes iniciar sesión";
  if (response.status === 403) return "No tienes permisos";
  if (response.status >= 500) return "Error del servidor";
  return `Error en la solicitud (${response.status})`;
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

export type CustomerListResponse = {
  items: Customer[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export const adminCustomersApi = {
  list(params?: {
    page?: number;
    page_size?: number;
    q?: string;
    is_active?: boolean;
  }) {
    const qs = new URLSearchParams();
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 20));
    if (params?.q) qs.set("q", params.q);
    if (params?.is_active !== undefined) {
      qs.set("is_active", String(params.is_active));
    }
    return request<CustomerListResponse>(`/api/v1/admin/customers?${qs}`);
  },
  setCashOnDelivery(userId: string, allow: boolean) {
    return request<Customer>(`/api/v1/admin/customers/${userId}/cash-on-delivery`, {
      method: "PATCH",
      body: JSON.stringify({ allow_cash_on_delivery: allow }),
    });
  },
  setActive(userId: string, isActive: boolean) {
    return request<Customer>(`/api/v1/admin/customers/${userId}/active`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    });
  },
};
