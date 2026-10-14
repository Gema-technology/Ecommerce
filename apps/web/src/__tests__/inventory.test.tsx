import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminInventoryPage from "@/app/admin/inventory/page";
import InventoryDetailPage from "@/app/admin/inventory/[productId]/page";
import { AuthProvider } from "@/components/auth/AuthProvider";
import type { User } from "@/lib/auth-api";
import type { InventoryItem } from "@/lib/inventory-api";

const replace = vi.fn();
const push = vi.fn();
const searchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, prefetch: vi.fn() }),
  usePathname: () => "/admin/inventory",
  useParams: () => ({ productId: "p1" }),
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

const mainLocation = {
  id: "loc1",
  name: "Bodega Principal",
  code: "MAIN",
  description: null,
  city: "Ibarra",
  province: "Imbabura",
  country: "Ecuador",
  is_active: true,
};

function baseInventory(): InventoryItem {
  return {
    id: "inv1",
    product_id: "p1",
    product_name: "RTX 4060",
    product_sku: "GPU-4060",
    location: {
      id: "loc1",
      name: "Bodega Principal",
      code: "MAIN",
      city: "Ibarra",
    },
    quantity: 10,
    reserved_quantity: 2,
    available_quantity: 8,
    reorder_point: 3,
    reorder_quantity: 10,
  };
}

const lowStockItem: InventoryItem = {
  ...baseInventory(),
  id: "inv2",
  product_id: "p2",
  product_name: "Mouse",
  product_sku: "MOU-1",
  quantity: 2,
  reserved_quantity: 0,
  available_quantity: 2,
  reorder_point: 5,
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch(session: User | null) {
  let current = baseInventory();
  const movements = [
    {
      id: "m1",
      inventory_id: "inv1",
      type: "PURCHASE",
      quantity: 10,
      direction: "IN",
      signed_quantity: 10,
      reference_type: null,
      reference_id: null,
      notes: "Initial",
      created_by: "2",
      created_by_email: "admin@example.com",
      created_at: "2026-01-01T00:00:00Z",
    },
  ];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();

      if (url.includes("/auth/me")) {
        return session ? json(session) : new Response(null, { status: 401 });
      }
      if (url.includes("/admin/locations") && method === "GET") {
        return json([mainLocation]);
      }
      if (url.includes("/admin/inventory/low-stock")) {
        return json([lowStockItem]);
      }
      if (url.includes("/admin/inventory/p1/movements")) {
        return json({
          items: movements,
          page: 1,
          page_size: 20,
          total: movements.length,
          total_pages: 1,
        });
      }
      if (url.includes("/admin/inventory/p1/adjust") && method === "POST") {
        current = {
          ...current,
          quantity: current.quantity + 2,
          available_quantity: current.available_quantity + 2,
        };
        return json({
          inventory: current,
          movement: {
            id: "m2",
            inventory_id: "inv1",
            type: "ADJUSTMENT",
            quantity: 2,
            direction: "IN",
            signed_quantity: 2,
            reference_type: null,
            reference_id: null,
            notes: null,
            created_by: "2",
            created_by_email: "admin@example.com",
            created_at: "2026-01-02T00:00:00Z",
          },
        });
      }
      if (url.includes("/admin/inventory/p1/reserve") && method === "POST") {
        current = {
          ...current,
          reserved_quantity: current.reserved_quantity + 1,
          available_quantity: current.available_quantity - 1,
        };
        return json({
          inventory: current,
          movement: {
            id: "m3",
            inventory_id: "inv1",
            type: "RESERVATION",
            quantity: 1,
            direction: "IN",
            signed_quantity: 1,
            reference_type: null,
            reference_id: null,
            notes: null,
            created_by: "2",
            created_by_email: "admin@example.com",
            created_at: "2026-01-02T00:00:00Z",
          },
        });
      }
      if (url.match(/\/admin\/inventory\/p1$/) || url.includes("/admin/inventory/p1?")) {
        return json(current);
      }
      if (url.includes("/admin/inventory") && method === "GET") {
        return json([current, lowStockItem]);
      }
      return new Response(null, { status: 404 });
    }),
  );
}

beforeEach(() => {
  replace.mockReset();
  push.mockReset();
  Array.from(searchParams.keys()).forEach((k) => searchParams.delete(k));
  Element.prototype.scrollIntoView = vi.fn();
  vi.unstubAllGlobals();
});

describe("inventory frontend", () => {
  it("protects inventory for customer", async () => {
    stubFetch(customer);
    render(
      <AuthProvider>
        <AdminInventoryPage />
      </AuthProvider>,
    );
    expect(await screen.findByText(/acceso denegado/i)).toBeInTheDocument();
  });

  it("shows inventory dashboard with low stock", async () => {
    stubFetch(admin);
    render(
      <AuthProvider>
        <AdminInventoryPage />
      </AuthProvider>,
    );
    expect(await screen.findByRole("heading", { name: "Inventario" })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Bajo stock" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("Mouse")).toBeInTheDocument();
    expect(await screen.findByText("RTX 4060")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ubicaciones/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /inicializar inventario/i }),
    ).toBeInTheDocument();
  });

  it("shows inventory detail and movement history", async () => {
    stubFetch(admin);
    render(
      <AuthProvider>
        <InventoryDetailPage />
      </AuthProvider>,
    );
    expect(await screen.findByText("Disponible")).toBeInTheDocument();
    expect(await screen.findByText("Historial de movimientos")).toBeInTheDocument();
    expect(await screen.findByText("Compra / ingreso")).toBeInTheDocument();
    expect(screen.getByText("admin@example.com")).toBeInTheDocument();
  });

  it("runs adjustment from detail", async () => {
    const user = userEvent.setup();
    stubFetch(admin);
    render(
      <AuthProvider>
        <InventoryDetailPage />
      </AuthProvider>,
    );
    await screen.findByText("Historial de movimientos");
    await user.click(screen.getByRole("button", { name: /nuevo movimiento/i }));
    await screen.findByRole("heading", { name: "Nuevo movimiento" });
    await user.click(screen.getByLabelText(/^tipo$/i));
    await user.click(await screen.findByRole("option", { name: /ajuste/i }));
    const amount = screen.getByLabelText(/delta/i);
    await user.clear(amount);
    await user.type(amount, "2");
    await user.click(screen.getByRole("button", { name: /ejecutar/i }));
    await waitFor(() => {
      expect(screen.getByText("12")).toBeInTheDocument();
    });
  });

  it("runs reservation from detail", async () => {
    const user = userEvent.setup();
    stubFetch(admin);
    render(
      <AuthProvider>
        <InventoryDetailPage />
      </AuthProvider>,
    );
    await screen.findByText("Historial de movimientos");
    await user.click(screen.getByRole("button", { name: /nuevo movimiento/i }));
    await screen.findByRole("heading", { name: "Nuevo movimiento" });
    await user.click(screen.getByLabelText(/^tipo$/i));
    await user.click(await screen.findByRole("option", { name: /^reserva$/i }));
    await user.click(screen.getByRole("button", { name: /ejecutar/i }));
    await waitFor(() => {
      expect(screen.getByText("7")).toBeInTheDocument();
    });
  });
});
