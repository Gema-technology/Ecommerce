import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "@/components/auth/AuthProvider";
import { CartProvider } from "@/components/cart/CartProvider";
import { CategoryCard } from "@/components/categories/CategoryCard";
import { ProductCard } from "@/components/products/ProductCard";
import { ProductFilters } from "@/components/products/ProductFilters";
import { ProductGrid } from "@/components/products/ProductGrid";
import { ProductSortSelect } from "@/components/products/ProductSort";
import { EmptyState } from "@/components/shared/EmptyState";
import { Pagination } from "@/components/shared/Pagination";
import { SearchBar } from "@/components/shared/SearchBar";
import { StoreHeader } from "@/components/layout/StoreHeader";
import type { Product } from "@/lib/catalog-types";
import {
  availabilityLabel,
  formatPrice,
  formatSpecKey,
} from "@/lib/catalog-types";

const push = vi.fn();
const searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => searchParams,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...rest
  }: {
    children: React.ReactNode;
    href: string;
  } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...rest}>
      {children}
    </a>
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

const product: Product = {
  id: "p1",
  sku: "LAP-1",
  name: "ASUS TUF Gaming A15",
  slug: "asus-tuf-gaming-a15",
  short_description: "Laptop",
  description: "Desc",
  model: "A15",
  brand: { id: "b1", name: "ASUS", slug: "asus" },
  category: { id: "c1", name: "Laptops", slug: "laptops" },
  specifications: { ram: "16 GB" },
  weight: null,
  warranty_months: 12,
  is_active: true,
  images: [
    {
      url: "/laptop.jpg",
      alt_text: "ASUS TUF",
      sort_order: 0,
      is_primary: true,
    },
  ],
  price: { amount: "999.00", currency: "USD", price_type: "RETAIL" },
  availability: "LOW_STOCK",
};

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <AuthProvider>
      <CartProvider>{ui}</CartProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  push.mockReset();
  Array.from(searchParams.keys()).forEach((k) => searchParams.delete(k));
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(null, { status: 401 })),
  );
});

describe("storefront MVP", () => {
  it("renders store header navigation and cart control", async () => {
    const user = userEvent.setup();
    renderWithProviders(<StoreHeader />);
    expect(
      screen.getByRole("link", { name: /GEMA Technology/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Productos" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Categorías" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Marcas" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ofertas" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /abrir carrito/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /buscar productos/i }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /abrir cuenta/i }));
    expect(
      await screen.findByRole("menuitem", { name: /iniciar sesión/i }),
    ).toBeInTheDocument();
  });

  it("search bar navigates to /products?search=", async () => {
    const user = userEvent.setup();
    render(<SearchBar id="test-search" />);
    await user.type(screen.getByLabelText(/buscar productos/i), "asus");
    await user.click(screen.getByRole("button", { name: /buscar/i }));
    expect(push).toHaveBeenCalledWith("/products?search=asus");
  });

  it("product grid lists cards", () => {
    render(<ProductGrid products={[product]} />);
    expect(screen.getByText("ASUS TUF Gaming A15")).toBeInTheDocument();
    expect(screen.getByAltText("ASUS TUF")).toBeInTheDocument();
    expect(screen.getByText("Stock bajo")).toBeInTheDocument();
  });

  it("availability labels cover public statuses", () => {
    expect(availabilityLabel("IN_STOCK")).toBe("Disponible");
    expect(availabilityLabel("LOW_STOCK")).toBe("Stock bajo");
    expect(availabilityLabel("OUT_OF_STOCK")).toBe("Agotado");
    expect(availabilityLabel("UNKNOWN")).toBe("Consultar disponibilidad");
    expect(availabilityLabel(undefined)).toBe("Consultar disponibilidad");
  });

  it("filters push category brand and search to URL", async () => {
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
    await user.click(screen.getByRole("button", { name: /categoría/i }));
    await user.click(await screen.findByRole("option", { name: /laptops/i }));
    await waitFor(() => {
      expect(screen.getByLabelText(/marca/i)).toBeEnabled();
    });
    await user.click(screen.getByLabelText(/marca/i));
    await user.click(await screen.findByRole("option", { name: /^asus$/i }));
    await user.type(screen.getByLabelText(/^buscar$/i), "tuf");
    await user.click(screen.getByRole("button", { name: /aplicar/i }));
    const called = String(push.mock.calls[0][0]);
    expect(called).toContain("category=laptops");
    expect(called).toContain("brand=asus");
    expect(called).toContain("search=tuf");
  });

  it("sort select updates URL", async () => {
    const user = userEvent.setup();
    render(<ProductSortSelect />);
    await user.click(screen.getByRole("button", { name: "Precio ↑" }));
    expect(push).toHaveBeenCalledWith("/products?sort=price_asc");
  });

  it("pagination keeps query and updates page", () => {
    searchParams.set("brand", "asus");
    searchParams.set("page", "2");
    render(<Pagination page={2} totalPages={5} />);
    expect(screen.getByRole("link", { name: "Anterior" })).toHaveAttribute(
      "href",
      expect.stringContaining("brand=asus"),
    );
    expect(screen.getByRole("link", { name: "Siguiente" })).toHaveAttribute(
      "href",
      expect.stringContaining("page=3"),
    );
  });

  it("empty state offers clear filters action", () => {
    render(
      <EmptyState title="No encontramos productos con esos filtros." />,
    );
    expect(
      screen.getByRole("link", { name: "Limpiar filtros" }),
    ).toHaveAttribute("href", "/products");
  });

  it("category card links to slug route", () => {
    render(
      <CategoryCard
        category={{
          id: "c1",
          name: "Laptops",
          slug: "laptops",
          description: "Portátiles",
          image_url: null,
          parent_id: null,
          is_active: true,
        }}
      />,
    );
    expect(screen.getByRole("link", { name: /laptops/i })).toHaveAttribute(
      "href",
      "/categories/laptops",
    );
  });

  it("formats price and out of stock on card", () => {
    render(
      <ProductCard
        product={{
          ...product,
          price: { amount: "10.5", currency: "USD", price_type: "RETAIL" },
          availability: "OUT_OF_STOCK",
        }}
      />,
    );
    expect(
      screen.getByText(
        formatPrice({ amount: "10.5", currency: "USD", price_type: "RETAIL" })!,
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Agotado")).toBeInTheDocument();
    expect(formatSpecKey("storage")).toBe("Almacenamiento");
  });
});
