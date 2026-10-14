import { ApiError } from "@/lib/auth-api";

export type StoreConfig = {
  business_name: string;
  business_ruc: string;
  business_phone: string;
  business_address: string;
  business_email: string;
  bank_name: string;
  bank_account_type: "Ahorros" | "Corriente" | string;
  bank_account_number: string;
  bank_account_holder: string;
  bank_account_id: string;
  bank_transfer_instructions: string;
  shipping_enabled: boolean;
  shipping_flat_rate: string;
  shipping_free_threshold: string | null;
  shipping_province_rates: Record<string, string>;
  updated_at: string | null;
};

export type StoreConfigUpdate = {
  business_name: string;
  business_ruc: string;
  business_phone: string;
  business_address: string;
  business_email: string;
  bank_name: string;
  bank_account_type: "Ahorros" | "Corriente";
  bank_account_number: string;
  bank_account_holder: string;
  bank_account_id: string;
  bank_transfer_instructions: string;
  shipping_enabled: boolean;
  shipping_flat_rate: string;
  shipping_free_threshold: string | null;
  shipping_province_rates: Record<string, string>;
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

export const storeConfigApi = {
  get() {
    return request<StoreConfig>("/api/v1/admin/store-config");
  },
  update(payload: StoreConfigUpdate) {
    return request<StoreConfig>("/api/v1/admin/store-config", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
};
