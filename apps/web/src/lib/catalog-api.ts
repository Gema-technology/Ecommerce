import { ApiError } from "@/lib/auth-api";
import type {
  Brand,
  Category,
  Product,
  ProductListResponse,
  ProductSort,
} from "@/lib/catalog-types";

export type {
  AvailabilityStatus,
  Brand,
  Category,
  Product,
  ProductImage,
  ProductListResponse,
  ProductSort,
  PublicPrice,
} from "@/lib/catalog-types";

export {
  availabilityLabel,
  formatPrice,
  formatSavings,
  formatSpecKey,
  getCompareAtPrice,
  shippingLabel,
} from "@/lib/catalog-types";

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

function isProductionBuild(): boolean {
  return process.env.NEXT_PHASE === "phase-production-build";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Avoid hanging `next build` when the API is down: Next's patched fetch can
  // keep static/dynamic workers alive even after a Promise.race timeout.
  if (typeof window === "undefined" && isProductionBuild()) {
    throw new ApiError(503, "API no disponible");
  }

  const url = `${apiBase()}${path}`;
  const isServer = typeof window === "undefined";
  const controller = isServer ? new AbortController() : null;
  const timer = controller
    ? setTimeout(() => controller.abort(), 5_000)
    : null;

  try {
    const response = await fetch(url, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      // Catalog reads must not use ISR revalidate during SSR — that keeps
      // build workers waiting on unreachable API hosts.
      cache: "no-store",
      ...(controller ? { signal: controller.signal } : {}),
    } as RequestInit);
    if (!response.ok) {
      throw new ApiError(response.status, await parseError(response));
    }
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(503, "API no disponible");
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export type ProductQuery = {
  category?: string;
  brand?: string;
  search?: string;
  sort?: ProductSort;
  min_price?: string | number;
  max_price?: string | number;
  page?: number;
  page_size?: number;
  is_active?: boolean;
};

function toQuery(params: Record<string, string | number | undefined>) {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== "") search.set(k, String(v));
  });
  return search.toString();
}

export const catalogApi = {
  listCategories(admin = false) {
    return request<Category[]>(admin ? "/api/v1/admin/categories" : "/api/v1/categories");
  },
  getCategory(slug: string) {
    return request<Category>(`/api/v1/categories/${slug}`);
  },
  createCategory(payload: Partial<Category> & { name: string }) {
    return request<Category>("/api/v1/admin/categories", {
      method: "POST",
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  },
  updateCategory(id: string, payload: Partial<Category>) {
    return request<Category>(`/api/v1/admin/categories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  },
  deleteCategory(id: string) {
    return request<Category>(`/api/v1/admin/categories/${id}`, {
      method: "DELETE",
      cache: "no-store",
    });
  },

  listBrandsPublic(options?: { category?: string }) {
    const qs = toQuery({ category: options?.category });
    return request<Brand[]>(qs ? `/api/v1/brands?${qs}` : "/api/v1/brands");
  },
  listBrandsAdmin(options?: {
    category?: string;
    q?: string;
    is_active?: boolean;
    page?: number;
    page_size?: number;
  }) {
    const qs = toQuery({
      category: options?.category,
      q: options?.q,
      is_active:
        options?.is_active === undefined ? undefined : String(options.is_active),
      page: options?.page ?? 1,
      page_size: options?.page_size ?? 20,
    });
    return request<{
      items: Brand[];
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    }>(`/api/v1/admin/brands?${qs}`);
  },
  /** @deprecated Prefer listBrandsPublic / listBrandsAdmin */
  listBrands(admin = false, options?: { category?: string }) {
    if (admin) {
      return this.listBrandsAdmin({
        category: options?.category,
        page: 1,
        page_size: 100,
      }).then((data) => data.items);
    }
    return this.listBrandsPublic(options);
  },
  /** All brands for dropdowns (admin, large page). */
  listAllBrandsAdmin(options?: { category?: string }) {
    return this.listBrandsAdmin({
      ...options,
      page: 1,
      page_size: 100,
    }).then((data) => data.items);
  },
  createBrand(payload: Partial<Brand> & { name: string }) {
    return request<Brand>("/api/v1/admin/brands", {
      method: "POST",
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  },
  updateBrand(id: string, payload: Partial<Brand>) {
    return request<Brand>(`/api/v1/admin/brands/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  },
  deleteBrand(id: string) {
    return request<Brand>(`/api/v1/admin/brands/${id}`, {
      method: "DELETE",
      cache: "no-store",
    });
  },

  listProducts(params: ProductQuery = {}, admin = false) {
    const qs = toQuery({
      category: params.category,
      brand: params.brand,
      search: params.search,
      sort: params.sort,
      min_price: params.min_price,
      max_price: params.max_price,
      page: params.page,
      page_size: params.page_size,
      is_active: params.is_active === undefined ? undefined : String(params.is_active),
    });
    const base = admin ? "/api/v1/admin/products" : "/api/v1/products";
    return request<ProductListResponse>(qs ? `${base}?${qs}` : base);
  },
  getProduct(slug: string) {
    return request<Product>(`/api/v1/products/${slug}`);
  },
  createProduct(payload: Record<string, unknown>) {
    return request<Product>("/api/v1/admin/products", {
      method: "POST",
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  },
  updateProduct(id: string, payload: Record<string, unknown>) {
    return request<Product>(`/api/v1/admin/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
      cache: "no-store",
    });
  },
  deleteProduct(id: string) {
    return request<Product>(`/api/v1/admin/products/${id}`, {
      method: "DELETE",
      cache: "no-store",
    });
  },
};
