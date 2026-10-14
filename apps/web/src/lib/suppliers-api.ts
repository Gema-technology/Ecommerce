import { ApiError } from "@/lib/auth-api";

export type TaxIdType = "RUC" | "CEDULA" | "PASSPORT" | "OTHER";
export type CurrencyCode = "USD";
export type SupplierAvailability =
  | "IN_STOCK"
  | "LOW_STOCK"
  | "OUT_OF_STOCK"
  | "PREORDER"
  | "UNKNOWN";

export type Supplier = {
  id: string;
  business_name: string;
  commercial_name: string | null;
  tax_id: string;
  tax_id_type: TaxIdType;
  email: string | null;
  phone: string | null;
  website_url: string | null;
  address: string | null;
  city: string | null;
  province: string | null;
  country: string;
  contact_name: string | null;
  notes: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type SupplierProduct = {
  id: string;
  supplier_id: string;
  product_id: string;
  supplier_sku: string | null;
  supplier_product_name: string | null;
  cost: string;
  currency: CurrencyCode;
  availability: SupplierAvailability;
  lead_time_days: number | null;
  minimum_order_quantity: number;
  supplier_url: string | null;
  last_checked_at: string | null;
  is_active: boolean;
  product_name?: string | null;
  product_sku?: string | null;
};

export type ProductSuppliersResponse = {
  product: { id: string; name: string; sku: string };
  suppliers: Array<{
    supplier_product_id: string;
    supplier_id: string;
    supplier_name: string;
    supplier_sku: string | null;
    cost: string;
    currency: CurrencyCode;
    availability: SupplierAvailability;
    lead_time_days: number | null;
    minimum_order_quantity: number;
    supplier_url: string | null;
    last_checked_at: string | null;
    is_active: boolean;
  }>;
};

export type SupplierCreatePayload = {
  business_name: string;
  commercial_name?: string | null;
  tax_id: string;
  tax_id_type: TaxIdType;
  email?: string | null;
  phone?: string | null;
  website_url?: string | null;
  address?: string | null;
  city?: string | null;
  province?: string | null;
  country?: string;
  contact_name?: string | null;
  notes?: string | null;
  is_active?: boolean;
};

export type SupplierProductPayload = {
  product_id?: string;
  supplier_id?: string;
  supplier_sku?: string | null;
  supplier_product_name?: string | null;
  cost: string;
  currency?: CurrencyCode;
  availability?: SupplierAvailability;
  lead_time_days?: number | null;
  minimum_order_quantity?: number;
  supplier_url?: string | null;
  is_active?: boolean;
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

export const suppliersApi = {
  list(params?: {
    search?: string;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }) {
    const qs = new URLSearchParams();
    if (params?.search) qs.set("search", params.search);
    if (params?.is_active !== undefined) qs.set("is_active", String(params.is_active));
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 20));
    return request<{
      items: Supplier[];
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    }>(`/api/v1/admin/suppliers?${qs}`);
  },
  get(id: string) {
    return request<Supplier>(`/api/v1/admin/suppliers/${id}`);
  },
  create(payload: SupplierCreatePayload) {
    return request<Supplier>("/api/v1/admin/suppliers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  update(id: string, payload: Partial<SupplierCreatePayload>) {
    return request<Supplier>(`/api/v1/admin/suppliers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  remove(id: string) {
    return request<Supplier>(`/api/v1/admin/suppliers/${id}`, { method: "DELETE" });
  },
  listProducts(supplierId: string) {
    return request<SupplierProduct[]>(`/api/v1/admin/suppliers/${supplierId}/products`);
  },
  addProduct(supplierId: string, payload: SupplierProductPayload & { product_id: string }) {
    return request<SupplierProduct>(`/api/v1/admin/suppliers/${supplierId}/products`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateProduct(
    supplierId: string,
    supplierProductId: string,
    payload: Partial<SupplierProductPayload> & { mark_checked?: boolean },
  ) {
    return request<SupplierProduct>(
      `/api/v1/admin/suppliers/${supplierId}/products/${supplierProductId}`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  },
  removeProduct(supplierId: string, supplierProductId: string) {
    return request<SupplierProduct>(
      `/api/v1/admin/suppliers/${supplierId}/products/${supplierProductId}`,
      { method: "DELETE" },
    );
  },
  listForProduct(productId: string) {
    return request<ProductSuppliersResponse>(`/api/v1/admin/products/${productId}/suppliers`);
  },
  linkToProduct(productId: string, payload: SupplierProductPayload & { supplier_id: string }) {
    return request<SupplierProduct>(`/api/v1/admin/products/${productId}/suppliers`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
};
