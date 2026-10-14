import { ApiError } from "@/lib/auth-api";

export type PricingConfig = {
  min_margin: string;
  rec_margin: string;
  high_margin: string;
  card_cost: string;
  default_iva: string;
  updated_at: string | null;
};

export type QuoteProduct = {
  id: string;
  name: string;
  category: string | null;
  cost_price: string;
  other_costs: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  cost_real: string;
  price_min: string;
  price_rec: string;
  price_high: string;
};

export type QuoteProductListResponse = {
  items: QuoteProduct[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type QuoteItem = {
  id: string;
  product_id: string | null;
  product_name: string;
  tier: string | null;
  quantity: number;
  unit_price: string;
  line_total: string;
};

export type Quote = {
  id: string;
  number: string;
  client_name: string;
  client_id_number: string | null;
  client_phone: string | null;
  client_email: string | null;
  client_address: string | null;
  iva_pct: string;
  subtotal: string;
  iva_amount: string;
  total: string;
  status: string;
  valid_until: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  items: QuoteItem[];
  created_by_email: string | null;
};

export type QuoteListResponse = {
  items: Quote[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type QuoteItemInput = {
  product_id?: string | null;
  product_name?: string | null;
  tier?: "min" | "rec" | "high" | "manual";
  quantity: number;
  unit_price?: string | null;
};

export type QuoteCreateInput = {
  client_name: string;
  client_id_number?: string | null;
  client_phone?: string | null;
  client_email?: string | null;
  client_address?: string | null;
  iva_pct?: string | null;
  valid_until?: string | null;
  notes?: string | null;
  status?: string;
  items: QuoteItemInput[];
};

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_ORIGIN?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  }
  return "";
}

async function parseError(response: Response): Promise<string> {
  const fallback = response.statusText || `Error ${response.status}`;
  try {
    const text = await response.text();
    if (!text) return fallback;
    let data: { detail?: unknown };
    try {
      data = JSON.parse(text) as { detail?: unknown };
    } catch {
      return text.slice(0, 200) || fallback;
    }
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
    return fallback;
  } catch {
    return fallback;
  }
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
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function quoteStatusLabel(status: string): string {
  switch (status) {
    case "draft":
      return "Borrador";
    case "sent":
      return "Enviada";
    case "accepted":
      return "Aceptada";
    case "rejected":
      return "Rechazada";
    case "expired":
      return "Expirada";
    default:
      return status;
  }
}

export function tierLabel(tier: string): string {
  switch (tier) {
    case "min":
      return "Mínimo";
    case "rec":
      return "Recomendado";
    case "high":
      return "Alto";
    case "manual":
      return "Manual";
    default:
      return tier;
  }
}

export function formatUsd(amount: string | number): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  if (Number.isNaN(num)) return `$${amount}`;
  return new Intl.NumberFormat("es-EC", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(num);
}

export function marginToPercent(margin: string): number {
  return Math.round(parseFloat(margin) * 1000) / 10;
}

export function percentToMargin(pct: number): string {
  return (pct / 100).toFixed(4);
}

/** Client-side preview totals (backend recalculates on save). */
export function previewQuoteTotals(
  lines: { quantity: number; unitPrice: number }[],
  ivaPct: number,
): { subtotal: number; iva: number; total: number } {
  const subtotal = lines.reduce((sum, line) => sum + line.quantity * line.unitPrice, 0);
  const iva = subtotal * ivaPct;
  return { subtotal, iva, total: subtotal + iva };
}

export const quotesApi = {
  getPricingConfig() {
    return request<PricingConfig>("/api/v1/admin/pricing-config");
  },
  updatePricingConfig(payload: Partial<Record<keyof PricingConfig, string>>) {
    return request<PricingConfig>("/api/v1/admin/pricing-config", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  listProducts(params?: { q?: string; page?: number; page_size?: number; active_only?: boolean }) {
    const search = new URLSearchParams();
    if (params?.q) search.set("q", params.q);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    if (params?.active_only) search.set("active_only", "true");
    const qs = search.toString();
    return request<QuoteProductListResponse>(
      `/api/v1/admin/catalog/products${qs ? `?${qs}` : ""}`,
    );
  },
  createProduct(payload: {
    name: string;
    category?: string | null;
    cost_price: string;
    other_costs?: string;
    is_active?: boolean;
  }) {
    return request<QuoteProduct>("/api/v1/admin/catalog/products", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateProduct(
    id: string,
    payload: Partial<{
      name: string;
      category: string | null;
      cost_price: string;
      other_costs: string;
      is_active: boolean;
    }>,
  ) {
    return request<QuoteProduct>(`/api/v1/admin/catalog/products/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  deleteProduct(id: string) {
    return request<void>(`/api/v1/admin/catalog/products/${id}`, { method: "DELETE" });
  },
  listQuotes(params?: {
    status?: string;
    client?: string;
    date_from?: string;
    date_to?: string;
    page?: number;
    page_size?: number;
  }) {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.client) search.set("client", params.client);
    if (params?.date_from) search.set("date_from", params.date_from);
    if (params?.date_to) search.set("date_to", params.date_to);
    if (params?.page) search.set("page", String(params.page));
    if (params?.page_size) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return request<QuoteListResponse>(`/api/v1/admin/quotes${qs ? `?${qs}` : ""}`);
  },
  getQuote(id: string) {
    return request<Quote>(`/api/v1/admin/quotes/${id}`);
  },
  createQuote(payload: QuoteCreateInput) {
    return request<Quote>("/api/v1/admin/quotes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateQuote(id: string, payload: Partial<QuoteCreateInput> & { status?: string }) {
    return request<Quote>(`/api/v1/admin/quotes/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  deleteQuote(id: string) {
    return request<void>(`/api/v1/admin/quotes/${id}`, { method: "DELETE" });
  },
  pdfUrl(id: string): string {
    return `${apiBase()}/api/v1/admin/quotes/${id}/pdf`;
  },
};
