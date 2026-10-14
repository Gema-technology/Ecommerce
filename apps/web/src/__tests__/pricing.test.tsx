import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminProductsPage from "@/app/admin/products/page";
import { ProductPricingPanel } from "@/components/admin/ProductPricingPanel";
import { ProductCard } from "@/components/products/ProductCard";
import { ProductFilters } from "@/components/products/ProductFilters";
import { AuthProvider } from "@/components/auth/AuthProvider";
import type { User } from "@/lib/auth-api";
import type { Product } from "@/lib/catalog-types";
import { formatPrice } from "@/lib/catalog-types";

const replace = vi.fn();
const push = vi.fn();
const searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, prefetch: vi.fn() }),
  usePathname: () => "/products",
  useParams: () => ({ slug: "asus-tuf", id: "p1" }),
  useSearchParams: () => searchParams,
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("@/lib/catalog-api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/catalog-api")>(
    "@/lib/catalog-api",
  );
  return {
    ...actual,
    catalogApi: {
      ...actual.catalogApi,
      listBrands: vi.fn(async () => [
        {
          id: "b1",
          name: "ASUS",
          slug: "asus",
          description: null,
          logo_url: null,
          website_url: null,
          is_active: true,
          category_ids: ["c1"],
        },
      ]),
    },
  };
});

const admin: User = {
  id: "2",
  email: "admin@example.com",
  first_name: "Admin",
  last_name: "User",
  phone: null,
  is_active: true,
  email_verified: true,
  allow_cash_on_delivery: false,
  roles: ["ADMIN"],
};

const customer: User = {
  ...admin,
  id: "1",
  email: "customer@example.com",
  allow_cash_on_delivery: false,
  roles: ["CUSTOMER"],
};

const pricedProduct: Product = {
  id: "p1",
  sku: "LAP-1",
  name: "ASUS TUF",
  slug: "asus-tuf",
  short_description: "Laptop",
  description: "Desc",
  model: "A15",
  brand: { id: "b1", name: "ASUS", slug: "asus" },
  category: { id: "c1", name: "Laptops", slug: "laptops" },
  specifications: {},
  weight: null,
  warranty_months: 12,
  is_active: true,
  images: [],
  price: { amount: "1199.9900", currency: "USD", price_type: "RETAIL" },
  availability: "IN_STOCK",
};

const unpricedProduct: Product = {
  ...pricedProduct,
  id: "p2",
  name: "No Price SKU",
  slug: "no-price",
  sku: "NOP-1",
  price: null,
  availability: "UNKNOWN",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(session: User | null = null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.includes("/auth/me")) {
        return session ? json(session) : new Response(null, { status: 401 });
      }
      if (url.includes("/prices/current")) {
        return json({
          id: "pr1",
          product_id: "p1",
          price_type: "RETAIL",
          amount: "1199.9900",
          currency: "USD",
          starts_at: "2026-01-01T00:00:00Z",
          ends_at: null,
          is_active: true,
          cost_reference: "900.0000",
          supplier_product_id: null,
          created_by: "2",
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
          created_by_email: "admin@example.com",
          supplier_name: null,
        });
      }
      if (url.includes("/prices/history") || (url.includes("/prices") && method === "GET")) {
        return json([
          {
            id: "pr1",
            product_id: "p1",
            price_type: "RETAIL",
            amount: "1199.9900",
            currency: "USD",
            starts_at: "2026-01-01T00:00:00Z",
            ends_at: null,
            is_active: true,
            cost_reference: "900.0000",
            supplier_product_id: null,
            created_by: "2",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            created_by_email: "admin@example.com",
            supplier_name: null,
          },
        ]);
      }
      if (url.includes("/prices") && method === "POST") {
        return json(
          {
            id: "pr2",
            product_id: "p1",
            price_type: "RETAIL",
            amount: "1099.0000",
            currency: "USD",
            starts_at: "2026-08-01T00:00:00Z",
            ends_at: null,
            is_active: true,
            cost_reference: null,
            supplier_product_id: null,
            created_by: "2",
            created_at: "2026-07-28T00:00:00Z",
            updated_at: "2026-07-28T00:00:00Z",
            created_by_email: "admin@example.com",
            supplier_name: null,
          },
          201,
        );
      }
      if (url.includes("/margin")) {
        return json({
          sale_price: "1199.9900",
          cost: "900.0000",
          margin_amount: "299.9900",
          margin_percentage: "25.0000",
          cost_source: "TechDist",
        });
      }
      if (url.includes("/admin/products") || url.includes("/products")) {
        return json({
          items: [pricedProduct, unpricedProduct],
          page: 1,
          page_size: 12,
          total: 2,
          total_pages: 1,
        });
      }
      return new Response(null, { status: 404 });
    }),
  );
}

beforeEach(() => {
  replace.mockReset();
  push.mockReset();
  vi.unstubAllGlobals();
  Array.from(searchParams.keys()).forEach((k) => searchParams.delete(k));
});

describe("pricing frontend", () => {
  it("shows retail price and consultar precio on product cards", () => {
    const { rerender } = render(<ProductCard product={pricedProduct} />);
    expect(screen.getByText(formatPrice(pricedProduct.price)!)).toBeInTheDocument();
    rerender(<ProductCard product={unpricedProduct} />);
    expect(screen.getByText("Consultar precio")).toBeInTheDocument();
  });

  it("writes price filters to the URL", async () => {
    const user = userEvent.setup();
    render(
      <ProductFilters
        categories={[
          {
            id: "c1",
            name: "Laptops",
            slug: "laptops",
            description: null,
            image_url: null,
            parent_id: null,
            is_active: true,
          },
        ]}
        brands={[
          {
            id: "b1",
            name: "ASUS",
            slug: "asus",
            description: null,
            logo_url: null,
            website_url: null,
            is_active: true,
            category_ids: ["c1"],
          },
        ]}
      />,
    );
    await user.type(screen.getByLabelText(/precio mínimo/i), "500");
    await user.type(screen.getByLabelText(/precio máximo/i), "1200");
    await user.click(screen.getByRole("button", { name: /aplicar/i }));
    expect(push).toHaveBeenCalledWith(
      expect.stringMatching(/min_price=500/),
    );
    expect(push).toHaveBeenCalledWith(
      expect.stringMatching(/max_price=1200/),
    );
  });

  it("shows admin pricing for admin and denies customer on admin products", async () => {
    stubFetch(customer);
    const { unmount } = render(
      <AuthProvider>
        <AdminProductsPage />
      </AuthProvider>,
    );
    expect(await screen.findByText(/acceso denegado/i)).toBeInTheDocument();
    unmount();

    stubFetch(admin);
    render(
      <AuthProvider>
        <ProductPricingPanel productId="p1" />
      </AuthProvider>,
    );
    expect(await screen.findByText("Precio de venta actual")).toBeInTheDocument();
    expect(await screen.findByText("Historial de precios")).toBeInTheDocument();
  });

  it("creates price from admin panel", async () => {
    const user = userEvent.setup();
    stubFetch(admin);
    render(
      <AuthProvider>
        <ProductPricingPanel productId="p1" />
      </AuthProvider>,
    );
    expect(await screen.findByText("Historial de precios")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /crear precio/i }));
    const dialog = await screen.findByRole("dialog", { name: "Crear precio" });
    await user.type(within(dialog).getByLabelText(/amount/i), "1099");
    await user.click(within(dialog).getByRole("button", { name: /crear precio/i }));
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });
  });
});
