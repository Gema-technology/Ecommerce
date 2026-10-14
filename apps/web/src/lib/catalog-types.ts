export type AvailabilityStatus =
  | "IN_STOCK"
  | "LOW_STOCK"
  | "OUT_OF_STOCK"
  | "UNKNOWN";

export type ProductAvailability = AvailabilityStatus;

export type PublicPrice = {
  amount: string;
  currency: string;
  price_type: string;
  compare_at_amount?: string | null;
};

export type ProductPrice = PublicPrice;

export type ProductSpecification = Record<string, unknown>;

export type Category = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  image_url: string | null;
  parent_id: string | null;
  is_active: boolean;
};

export type Brand = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  website_url: string | null;
  is_active: boolean;
  /** Category IDs this brand is allowed to sell in (inherits to descendants). */
  category_ids: string[];
};

export type ProductImage = {
  id?: string;
  url: string;
  alt_text: string | null;
  sort_order: number;
  is_primary: boolean;
};

export type Product = {
  id: string;
  sku: string;
  name: string;
  slug: string;
  short_description: string | null;
  description: string | null;
  model: string | null;
  brand: { id: string; name: string; slug: string };
  category: { id: string; name: string; slug: string };
  specifications: Record<string, unknown>;
  weight: string | null;
  warranty_months: number | null;
  is_active: boolean;
  images: ProductImage[];
  price?: PublicPrice | null;
  availability?: AvailabilityStatus;
};

export type ProductListResponse = {
  items: Product[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type PaginatedResponse<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export type ProductSort =
  | "relevance"
  | "price_asc"
  | "price_desc"
  | "name_asc"
  | "name_desc"
  | "newest";

export function formatPrice(price: PublicPrice | null | undefined): string | null {
  if (!price) return null;
  const amount = Number(price.amount);
  if (Number.isNaN(amount)) return `${price.currency} ${price.amount}`;
  return new Intl.NumberFormat("es-EC", {
    style: "currency",
    currency: price.currency || "USD",
  }).format(amount);
}

export function formatMoneyAmount(
  amount: string | number | null | undefined,
  currency = "USD",
): string | null {
  if (amount === null || amount === undefined || amount === "") return null;
  const n = Number(amount);
  if (Number.isNaN(n)) return `${currency} ${amount}`;
  return new Intl.NumberFormat("es-EC", {
    style: "currency",
    currency: currency || "USD",
  }).format(n);
}

export function getCompareAtPrice(
  price: PublicPrice | null | undefined,
): string | null {
  if (!price?.compare_at_amount) return null;
  const current = Number(price.amount);
  const compare = Number(price.compare_at_amount);
  if (Number.isNaN(compare) || Number.isNaN(current) || compare <= current) {
    return null;
  }
  return formatMoneyAmount(price.compare_at_amount, price.currency);
}

export function formatSavings(
  price: PublicPrice | null | undefined,
): string | null {
  if (!price?.compare_at_amount) return null;
  const current = Number(price.amount);
  const compare = Number(price.compare_at_amount);
  if (Number.isNaN(compare) || Number.isNaN(current) || compare <= current) {
    return null;
  }
  const saved = compare - current;
  const formatted = formatMoneyAmount(saved, price.currency);
  return formatted ? `Ahorras ${formatted}` : null;
}

export function availabilityLabel(
  status: AvailabilityStatus | null | undefined,
): string {
  switch (status) {
    case "IN_STOCK":
      return "Disponible";
    case "LOW_STOCK":
      return "Stock bajo";
    case "OUT_OF_STOCK":
      return "Agotado";
    default:
      return "Consultar disponibilidad";
  }
}

export function shippingLabel(
  status: AvailabilityStatus | null | undefined,
): string | null {
  switch (status) {
    case "IN_STOCK":
    case "LOW_STOCK":
      return "Envío disponible";
    case "OUT_OF_STOCK":
      return "Sin envío";
    default:
      return null;
  }
}

const SPEC_LABELS: Record<string, string> = {
  processor: "Procesador",
  cpu: "Procesador",
  ram: "RAM",
  memory: "Memoria",
  storage: "Almacenamiento",
  disk: "Almacenamiento",
  gpu: "GPU",
  graphics: "GPU",
  screen_size: "Pantalla",
  display: "Pantalla",
  resolution: "Resolución",
  weight: "Peso",
  warranty_months: "Garantía (meses)",
};

export function formatSpecKey(key: string): string {
  if (SPEC_LABELS[key]) return SPEC_LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
