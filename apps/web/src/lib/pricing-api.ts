import { ApiError } from "@/lib/auth-api";

export type PriceType = "RETAIL" | "WHOLESALE" | "PROMOTIONAL";

export type PublicPrice = {
  amount: string;
  currency: "USD";
  price_type: PriceType;
  compare_at_amount?: string | null;
};

export type ProductPrice = {
  id: string;
  product_id: string;
  price_type: PriceType;
  amount: string;
  currency: "USD";
  starts_at: string;
  ends_at: string | null;
  is_active: boolean;
  cost_reference: string | null;
  supplier_product_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  created_by_email: string | null;
  supplier_name: string | null;
};

export type MarginResult = {
  sale_price: string;
  cost: string;
  margin_amount: string;
  margin_percentage: string | null;
  cost_source: string | null;
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(503, "API no disponible");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const pricingApi = {
  list(productId: string) {
    return request<ProductPrice[]>(`/api/v1/admin/products/${productId}/prices`);
  },
  history(productId: string) {
    return request<ProductPrice[]>(`/api/v1/admin/products/${productId}/prices/history`);
  },
  current(productId: string, priceType: PriceType = "RETAIL") {
    return request<ProductPrice | null>(
      `/api/v1/admin/products/${productId}/prices/current?price_type=${priceType}`,
    );
  },
  create(
    productId: string,
    payload: {
      price_type: PriceType;
      amount: string;
      currency?: "USD";
      starts_at?: string;
      ends_at?: string | null;
      cost_reference?: string | null;
      supplier_product_id?: string | null;
    },
  ) {
    return request<ProductPrice>(`/api/v1/admin/products/${productId}/prices`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  update(
    productId: string,
    priceId: string,
    payload: Partial<{
      amount: string;
      starts_at: string;
      ends_at: string | null;
      is_active: boolean;
      cost_reference: string | null;
      supplier_product_id: string | null;
    }>,
  ) {
    return request<ProductPrice>(
      `/api/v1/admin/products/${productId}/prices/${priceId}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  },
  deactivate(productId: string, priceId: string) {
    return request<ProductPrice>(
      `/api/v1/admin/products/${productId}/prices/${priceId}`,
      { method: "DELETE" },
    );
  },
  margin(productId: string, supplierProductId?: string) {
    const qs = supplierProductId
      ? `?supplier_product_id=${supplierProductId}`
      : "";
    return request<MarginResult>(`/api/v1/admin/products/${productId}/margin${qs}`);
  },
};
