import { ApiError } from "@/lib/auth-api";

export type Location = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  city: string | null;
  province: string | null;
  country: string;
  is_active: boolean;
};

export type InventoryItem = {
  id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  location: { id: string; name: string; code: string; city: string | null };
  quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  reorder_point: number;
  reorder_quantity: number;
};

export type InventoryMovement = {
  id: string;
  inventory_id: string;
  type: string;
  quantity: number;
  direction: "IN" | "OUT";
  signed_quantity: number;
  reference_type: string | null;
  reference_id: string | null;
  notes: string | null;
  created_by: string;
  created_by_email: string | null;
  created_at: string;
};

export type MovementListResponse = {
  items: InventoryMovement[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type InventoryOperationResponse = {
  inventory: InventoryItem;
  movement: InventoryMovement;
};

export const MOVEMENT_TYPE_LABELS: Record<string, string> = {
  PURCHASE: "Compra / ingreso",
  SALE: "Venta manual",
  ADJUSTMENT: "Ajuste",
  RESERVATION: "Reserva",
  RELEASE: "Liberación",
  RETURN: "Devolución",
  DAMAGE: "Daño / merma",
};

export function movementTypeLabel(type: string): string {
  return MOVEMENT_TYPE_LABELS[type] ?? type;
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

type MovementPayload = {
  quantity: number;
  location_id?: string;
  notes?: string;
  reference_type?: string;
  reference_id?: string;
};

export type LocationListResponse = {
  items: Location[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type InventoryListResponse = {
  items: InventoryItem[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export const inventoryApi = {
  listLocations(params?: { q?: string; page?: number; page_size?: number }) {
    const qs = new URLSearchParams();
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 100));
    if (params?.q) qs.set("q", params.q);
    return request<LocationListResponse>(`/api/v1/admin/locations?${qs}`);
  },
  async listAllLocations() {
    const data = await this.listLocations({ page: 1, page_size: 100 });
    return data.items;
  },
  createLocation(payload: {
    name: string;
    code: string;
    description?: string | null;
    city?: string | null;
    province?: string | null;
    country?: string;
    is_active?: boolean;
  }) {
    return request<Location>("/api/v1/admin/locations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  list(params?: {
    location_id?: string;
    product_id?: string;
    q?: string;
    page?: number;
    page_size?: number;
  }) {
    const qs = new URLSearchParams();
    if (params?.location_id) qs.set("location_id", params.location_id);
    if (params?.product_id) qs.set("product_id", params.product_id);
    if (params?.q) qs.set("q", params.q);
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 20));
    return request<InventoryListResponse>(`/api/v1/admin/inventory?${qs}`);
  },
  lowStock(location_id?: string) {
    const qs = location_id ? `?location_id=${location_id}` : "";
    return request<InventoryItem[]>(`/api/v1/admin/inventory/low-stock${qs}`);
  },
  get(productId: string, location_id?: string) {
    const qs = location_id ? `?location_id=${location_id}` : "";
    return request<InventoryItem>(`/api/v1/admin/inventory/${productId}${qs}`);
  },
  create(payload: {
    product_id: string;
    location_id?: string;
    reorder_point?: number;
    reorder_quantity?: number;
  }) {
    return request<InventoryItem>("/api/v1/admin/inventory", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateThresholds(
    productId: string,
    payload: { reorder_point?: number; reorder_quantity?: number },
    location_id?: string,
  ) {
    const qs = location_id ? `?location_id=${location_id}` : "";
    return request<InventoryItem>(`/api/v1/admin/inventory/${productId}${qs}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  movements(
    productId: string,
    params?: {
      location_id?: string;
      movement_type?: string;
      page?: number;
      page_size?: number;
    },
  ) {
    const qs = new URLSearchParams();
    if (params?.location_id) qs.set("location_id", params.location_id);
    if (params?.movement_type) qs.set("movement_type", params.movement_type);
    if (params?.page) qs.set("page", String(params.page));
    if (params?.page_size) qs.set("page_size", String(params.page_size));
    const suffix = qs.toString() ? `?${qs}` : "";
    return request<MovementListResponse>(
      `/api/v1/admin/inventory/${productId}/movements${suffix}`,
    );
  },
  purchase(productId: string, payload: MovementPayload) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/purchase`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  sale(productId: string, payload: MovementPayload) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/sale`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  adjust(
    productId: string,
    payload: { delta: number; location_id?: string; notes?: string; reference_type?: string; reference_id?: string },
  ) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/adjust`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  reserve(productId: string, payload: MovementPayload) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/reserve`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  release(productId: string, payload: MovementPayload) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/release`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  returnStock(productId: string, payload: MovementPayload) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/return`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
  damage(productId: string, payload: MovementPayload) {
    return request<InventoryOperationResponse>(
      `/api/v1/admin/inventory/${productId}/damage`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  },
};
