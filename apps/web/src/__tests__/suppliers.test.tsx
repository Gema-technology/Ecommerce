import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminSuppliersPage from "@/app/admin/suppliers/page";
import NewSupplierPage from "@/app/admin/suppliers/new/page";
import SupplierDetailPage from "@/app/admin/suppliers/[id]/page";
import { ProductSuppliersPanel } from "@/components/admin/ProductSuppliersPanel";
import { AuthProvider } from "@/components/auth/AuthProvider";
import type { User } from "@/lib/auth-api";

const replace = vi.fn();
const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, prefetch: vi.fn() }),
  usePathname: () => "/admin/suppliers",
  useParams: () => ({ id: "s1" }),
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

const sampleSupplier = {
  id: "s1",
  business_name: "Distribuidora Tech SA",
  commercial_name: "TechDist",
  tax_id: "1790012345001",
  tax_id_type: "RUC",
  email: "ventas@techdist.example.com",
  phone: null,
  website_url: "https://techdist.example.com",
  address: null,
  city: "Quito",
  province: "Pichincha",
  country: "Ecuador",
  contact_name: "Ana",
  notes: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(session: User | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.includes("/auth/me")) {
        return session ? json(session) : new Response(null, { status: 401 });
      }
      if (url.includes("/admin/suppliers/s1/products") && method === "GET") {
        return json([
          {
            id: "sp1",
            supplier_id: "s1",
            product_id: "p1",
            supplier_sku: "RTX4060-A",
            supplier_product_name: "RTX 4060",
            cost: "280.0000",
            currency: "USD",
            availability: "IN_STOCK",
            lead_time_days: 2,
            minimum_order_quantity: 1,
            supplier_url: null,
            last_checked_at: "2026-01-01T00:00:00Z",
            is_active: true,
            product_name: "RTX 4060",
            product_sku: "GPU-4060",
          },
        ]);
      }
      if (url.match(/\/admin\/suppliers\/s1$/) && method === "GET") {
        return json(sampleSupplier);
      }
      if (url.includes("/admin/suppliers") && method === "POST") {
        return json({ ...sampleSupplier, id: "s2" }, 201);
      }
      if (url.includes("/admin/suppliers") && method === "GET") {
        return json([sampleSupplier]);
      }
      if (url.includes("/admin/products/") && url.includes("/suppliers") && method === "GET") {
        return json({
          product: { id: "p1", name: "RTX 4060", sku: "GPU-4060" },
          suppliers: [
            {
              supplier_product_id: "sp1",
              supplier_id: "s1",
              supplier_name: "TechDist",
              supplier_sku: "RTX4060-A",
              cost: "280.0000",
              currency: "USD",
              availability: "IN_STOCK",
              lead_time_days: 2,
              minimum_order_quantity: 1,
              supplier_url: null,
              last_checked_at: "2026-01-01T00:00:00Z",
              is_active: true,
            },
          ],
        });
      }
      if (url.includes("/admin/products") && method === "GET") {
        return json({
          items: [
            {
              id: "p1",
              sku: "GPU-4060",
              name: "RTX 4060",
              slug: "rtx-4060",
              short_description: null,
              description: null,
              model: null,
              brand: { id: "b1", name: "ASUS", slug: "asus" },
              category: { id: "c1", name: "GPUs", slug: "gpus" },
              specifications: {},
              weight: null,
              warranty_months: null,
              is_active: true,
              images: [],
            },
          ],
          page: 1,
          page_size: 100,
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
});

describe("suppliers frontend", () => {
  it("protects supplier list for customer", async () => {
    stubFetch(customer);
    render(
      <AuthProvider>
        <AdminSuppliersPage />
      </AuthProvider>,
    );
    expect(await screen.findByText(/acceso denegado/i)).toBeInTheDocument();
  });

  it("lists suppliers for admin", async () => {
    stubFetch(admin);
    render(
      <AuthProvider>
        <AdminSuppliersPage />
      </AuthProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Proveedores" })).toBeInTheDocument();
    expect(await screen.findByText("Distribuidora Tech SA")).toBeInTheDocument();
  });

  it("redirects legacy /new to suppliers list", async () => {
    stubFetch(admin);
    render(
      <AuthProvider>
        <NewSupplierPage />
      </AuthProvider>,
    );
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/admin/suppliers");
    });
  });

  it("opens supplier creation form in modal", async () => {
    const user = userEvent.setup();
    stubFetch(admin);
    render(
      <AuthProvider>
        <AdminSuppliersPage />
      </AuthProvider>,
    );
    await screen.findByRole("heading", { name: "Proveedores" });
    await user.click(screen.getByRole("button", { name: /nuevo proveedor/i }));
    expect(await screen.findByRole("heading", { name: "Nuevo proveedor" })).toBeInTheDocument();
    expect(screen.getByLabelText(/razón social/i)).toBeInTheDocument();
  });

  it("creates supplier and navigates", async () => {
    const user = userEvent.setup();
    stubFetch(admin);
    render(
      <AuthProvider>
        <AdminSuppliersPage />
      </AuthProvider>,
    );
    await screen.findByRole("heading", { name: "Proveedores" });
    await user.click(screen.getByRole("button", { name: /nuevo proveedor/i }));
    await screen.findByRole("heading", { name: "Nuevo proveedor" });
    await user.type(screen.getByLabelText(/razón social/i), "Nueva SA");
    await user.type(screen.getByLabelText(/^tax id$/i), "1790011111001");
    await user.click(screen.getByRole("button", { name: /crear proveedor/i }));
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/admin/suppliers/s2");
    });
  });

  it("shows supplier detail and products", async () => {
    stubFetch(admin);
    render(
      <AuthProvider>
        <SupplierDetailPage />
      </AuthProvider>,
    );
    expect(await screen.findByText("Información general")).toBeInTheDocument();
    expect(await screen.findByText("Productos ofrecidos")).toBeInTheDocument();
    expect(await screen.findByText("RTX4060-A")).toBeInTheDocument();
  });

  it("shows product suppliers panel", async () => {
    stubFetch(admin);
    render(
      <AuthProvider>
        <ProductSuppliersPanel productId="p1" />
      </AuthProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Proveedores" })).toBeInTheDocument();
    expect(await screen.findAllByText("TechDist")).not.toHaveLength(0);
    expect(screen.getByText("280.0000")).toBeInTheDocument();
  });
});
