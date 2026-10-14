import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminProductsPage from "@/app/admin/products/page";
import { ProductCard } from "@/components/products/ProductCard";
import { ProductGallery } from "@/components/products/ProductGallery";
import { ProductSpecifications } from "@/components/products/ProductSpecifications";
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
  useParams: () => ({ slug: "asus-tuf", id: "1" }),
  useSearchParams: () => searchParams,
}));

vi.mock("next/link", () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const customer: User = {
  id: "1",
  email: "customer@example.com",
  first_name: "John",
  last_name: "Doe",
  phone: null,
  is_active: true,
  email_verified: false,
  allow_cash_on_delivery: false,
  roles: ["CUSTOMER"],
};

const admin: User = {
  ...customer,
  id: "2",
  email: "admin@example.com",
  allow_cash_on_delivery: false,
  roles: ["ADMIN"],
};

const sampleProduct: Product = {
  id: "p1",
  sku: "LAP-1",
  name: "ASUS TUF",
  slug: "asus-tuf",
  short_description: "Laptop gaming",
  description: "Descripción completa",
  model: "A15",
  brand: { id: "b1", name: "ASUS", slug: "asus" },
  category: { id: "c1", name: "Laptops", slug: "laptops" },
  specifications: { ram: "16 GB", processor: "AMD Ryzen 7" },
  weight: null,
  warranty_months: 12,
  is_active: true,
  images: [],
  price: { amount: "1199.9900", currency: "USD", price_type: "RETAIL" },
  availability: "IN_STOCK",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubCatalogFetch(session: User | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/auth/me")) {
        return session ? json(session) : new Response(null, { status: 401 });
      }
      if (url.includes("/admin/products") || url.includes("/products")) {
        return json({
          items: [sampleProduct],
          page: 1,
          page_size: 12,
          total: 1,
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

describe("catalog frontend", () => {
  it("renders product card with price, brand, category and availability", () => {
    render(<ProductCard product={sampleProduct} />);
    expect(screen.getByText("ASUS TUF")).toBeInTheDocument();
    expect(screen.getByText("ASUS")).toBeInTheDocument();
    expect(screen.getByText("Laptops")).toBeInTheDocument();
    expect(screen.getByText("Disponible")).toBeInTheDocument();
    expect(screen.getByText(formatPrice(sampleProduct.price)!)).toBeInTheDocument();
  });

  it("shows placeholder and consultar precio without image/price", () => {
    const product: Product = {
      ...sampleProduct,
      images: [],
      price: null,
      availability: "UNKNOWN",
    };
    render(<ProductCard product={product} />);
    expect(screen.getByText("Sin imagen")).toBeInTheDocument();
    expect(screen.getByText("Consultar precio")).toBeInTheDocument();
    expect(screen.getByText("Consultar disponibilidad")).toBeInTheDocument();
  });

  it("renders friendly specifications labels", () => {
    render(
      <ProductSpecifications specifications={sampleProduct.specifications} />,
    );
    expect(screen.getByText("RAM")).toBeInTheDocument();
    expect(screen.getByText("16 GB")).toBeInTheDocument();
    expect(screen.getByText("Procesador")).toBeInTheDocument();
    expect(screen.getByText("AMD Ryzen 7")).toBeInTheDocument();
  });

  it("gallery shows placeholder without images and switches thumbnails", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <ProductGallery images={[]} productName="ASUS TUF" />,
    );
    expect(screen.getByText("Sin imágenes")).toBeInTheDocument();

    rerender(
      <ProductGallery
        productName="ASUS TUF"
        images={[
          {
            url: "/a.jpg",
            alt_text: "Principal",
            sort_order: 0,
            is_primary: true,
          },
          {
            url: "/b.jpg",
            alt_text: "Lateral",
            sort_order: 1,
            is_primary: false,
          },
        ]}
      />,
    );
    expect(screen.getAllByAltText("Principal").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /ver imagen 2/i }));
    expect(screen.getByRole("button", { name: /ver imagen 2/i })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(document.querySelector('img[src="/b.jpg"]')).toBeTruthy();
  });

  it("protects admin products for customer", async () => {
    stubCatalogFetch(customer);
    render(
      <AuthProvider>
        <AdminProductsPage />
      </AuthProvider>,
    );
    expect(await screen.findByText(/acceso denegado/i)).toBeInTheDocument();
  });

  it("allows admin products page", async () => {
    stubCatalogFetch(admin);
    render(
      <AuthProvider>
        <AdminProductsPage />
      </AuthProvider>,
    );
    expect(
      await screen.findByRole("heading", { name: "Productos" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("ASUS TUF")).toBeInTheDocument();
  });
});
