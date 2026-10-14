import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CheckoutPage from "@/app/checkout/page";
import OrdersPage from "@/app/orders/page";
import OrderDetailPage from "@/app/orders/[order_number]/page";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { CartProvider } from "@/components/cart/CartProvider";
import type { User } from "@/lib/auth-api";
import type { Cart } from "@/lib/cart-api";

const push = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/checkout",
  useParams: () => ({ order_number: "GEMA-20260728-000001" }),
  useSearchParams: () => new URLSearchParams(),
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

const filledCart: Cart = {
  id: "c1",
  status: "ACTIVE",
  items: [
    {
      id: "i1",
      quantity: 1,
      line_total: "100.0000",
      available: true,
      product: {
        id: "p1",
        name: "ASUS TUF",
        slug: "asus-tuf",
        sku: "LAP-1",
        image: null,
        price: { amount: "100.0000", currency: "USD" },
        is_active: true,
        availability: "IN_STOCK",
      },
    },
  ],
  subtotal: "100.0000",
  currency: "USD",
  item_count: 1,
};

const emptyCart: Cart = {
  id: "c1",
  status: "ACTIVE",
  items: [],
  subtotal: "0.0000",
  currency: "USD",
  item_count: 0,
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp(ui: React.ReactElement) {
  return render(
    <AuthProvider>
      <CartProvider>{ui}</CartProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  push.mockReset();
  vi.unstubAllGlobals();
});

async function pickCheckoutSelect(
  user: ReturnType<typeof userEvent.setup>,
  label: RegExp,
  optionLabel: string,
) {
  const field = screen.getByText(label).closest("label");
  expect(field).toBeTruthy();
  await user.click(within(field as HTMLElement).getByRole("button"));
  await user.click(await screen.findByRole("option", { name: optionLabel }));
}

async function advanceCheckoutToConfirm(
  user: ReturnType<typeof userEvent.setup>,
) {
  expect((await screen.findAllByText("ASUS TUF")).length).toBeGreaterThan(0);
  const phone = screen.queryByLabelText(/^teléfono$/i);
  if (phone) {
    await user.clear(phone);
    await user.type(phone, "0999999999");
  }
  await user.click(screen.getByRole("button", { name: /continuar/i }));
  await pickCheckoutSelect(user, /^provincia$/i, "Imbabura");
  await pickCheckoutSelect(user, /^ciudad$/i, "Ibarra");
  await user.type(screen.getByLabelText(/^dirección$/i), "Av. Teodoro Gomez 123");
  await user.click(screen.getByRole("button", { name: /continuar/i }));
  expect(
    await screen.findByRole("button", { name: /continuar al pago/i }),
  ).toBeInTheDocument();
}

const previewResponse = {
  currency: "USD",
  subtotal: "100.0000",
  tax_total: "0.0000",
  shipping_total: "5.0000",
  discount_total: "0.0000",
  total: "105.0000",
  shipping_method: "standard",
  tax_enabled: false,
  items: [
    {
      product_id: "p1",
      product_name: "ASUS TUF",
      sku: "LAP-1",
      quantity: 1,
      unit_price: "100.0000",
      line_total: "100.0000",
    },
  ],
};

describe("checkout and orders frontend", () => {
  it("shows empty cart on checkout", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) return json(emptyCart);
        return new Response(null, { status: 404 });
      }),
    );
    renderApp(<CheckoutPage />);
    expect(await screen.findByText(/tu carrito está vacío/i)).toBeInTheDocument();
  });

  it("reviews order and confirms checkout", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/me")) return json(customer);
      if (url.includes("/checkout/preview") && method === "POST") {
        return json(previewResponse);
      }
      if (url.includes("/checkout") && method === "POST" && !url.includes("preview")) {
        const body = JSON.parse(String(init?.body ?? "{}")) as {
          shipping_address?: { city?: string };
        };
        expect(body.shipping_address?.city).toBe("Ibarra");
        return json({
          order_id: "o1",
          order_number: "GEMA-20260728-000001",
          status: "PENDING_PAYMENT",
          currency: "USD",
          subtotal: "100.0000",
          tax_total: "0.0000",
          shipping_total: "0.0000",
          discount_total: "0.0000",
          total: "100.0000",
          items: [
            {
              product_id: "p1",
              product_name: "ASUS TUF",
              quantity: 1,
              unit_price: "100.0000",
              line_total: "100.0000",
            },
          ],
        });
      }
      if (url.includes("/cart")) return json(filledCart);
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp(<CheckoutPage />);
    expect(
      screen.getByRole("heading", { name: /finalizar compra/i }),
    ).toBeInTheDocument();
    await advanceCheckoutToConfirm(user);

    await user.click(screen.getByRole("button", { name: /continuar al pago/i }));
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith(
        "/orders/GEMA-20260728-000001/payment",
      );
    });
  });

  it("shows stock error from checkout", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/checkout/preview") && method === "POST") {
          return json(previewResponse);
        }
        if (url.includes("/checkout") && method === "POST" && !url.includes("preview")) {
          return json({ detail: "Insufficient available quantity" }, 409);
        }
        if (url.includes("/cart")) return json(filledCart);
        return new Response(null, { status: 404 });
      }),
    );
    renderApp(<CheckoutPage />);
    await advanceCheckoutToConfirm(user);
    await user.click(screen.getByRole("button", { name: /continuar al pago/i }));
    expect(
      await screen.findByText(/stock suficiente/i),
    ).toBeInTheDocument();
  });

  it("shows price changed state and syncs cart", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/me")) return json(customer);
      if (url.includes("/checkout/preview") && method === "POST") {
        return json(previewResponse);
      }
      if (url.includes("/checkout") && method === "POST" && !url.includes("preview")) {
        return json(
          {
            detail: {
              code: "PRICE_CHANGED",
              message: "One or more product prices have changed.",
              items: [
                {
                  product_id: "p1",
                  product_name: "ASUS TUF",
                  previous_unit_price: "999.0000",
                  current_unit_price: "1049.0000",
                  currency: "USD",
                },
              ],
            },
          },
          409,
        );
      }
      if (url.includes("/cart/sync-prices") && method === "POST") {
        return json({
          ...filledCart,
          items: [
            {
              ...filledCart.items[0],
              unit_price: "1049.0000",
              line_total: "1049.0000",
              quoted_unit_price: "1049.0000",
              product: {
                ...filledCart.items[0].product,
                price: { amount: "1049.0000", currency: "USD" },
              },
            },
          ],
          subtotal: "1049.0000",
        });
      }
      if (url.includes("/cart")) return json(filledCart);
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp(<CheckoutPage />);
    await advanceCheckoutToConfirm(user);
    await user.click(screen.getByRole("button", { name: /continuar al pago/i }));
    expect(await screen.findByText(/precio actualizado/i)).toBeInTheDocument();
    expect(screen.getByText(/\$999,00/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /actualizar carrito/i }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/cart/sync-prices"),
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("lists orders", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/orders")) {
          return json({
            items: [
              {
                id: "o1",
                order_number: "GEMA-20260728-000001",
                status: "PENDING_PAYMENT",
                currency: "USD",
                subtotal: "100.0000",
                tax_total: "0",
                shipping_total: "0",
                discount_total: "0",
                total: "100.0000",
                created_at: "2026-07-28T12:00:00Z",
                updated_at: "2026-07-28T12:00:00Z",
                items: [],
              },
            ],
            page: 1,
            page_size: 20,
            total: 1,
            total_pages: 1,
          });
        }
        if (url.includes("/cart")) return json(emptyCart);
        return new Response(null, { status: 404 });
      }),
    );
    renderApp(<OrdersPage />);
    expect(await screen.findByText("GEMA-20260728-000001")).toBeInTheDocument();
    expect(screen.getByText(/pendiente de pago/i)).toBeInTheDocument();
  });

  it("shows order detail success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/orders/by-number/")) {
          return json({
            id: "o1",
            order_number: "GEMA-20260728-000001",
            status: "PENDING_PAYMENT",
            currency: "USD",
            subtotal: "100.0000",
            tax_total: "0",
            shipping_total: "0",
            discount_total: "0",
            total: "100.0000",
            created_at: "2026-07-28T12:00:00Z",
            updated_at: "2026-07-28T12:00:00Z",
            items: [
              {
                id: "oi1",
                product_id: "p1",
                product_name_snapshot: "ASUS TUF",
                sku_snapshot: "LAP-1",
                unit_price: "100.0000",
                quantity: 1,
                line_total: "100.0000",
                created_at: "2026-07-28T12:00:00Z",
              },
            ],
          });
        }
        if (url.includes("/cart")) return json(emptyCart);
        return new Response(null, { status: 404 });
      }),
    );
    renderApp(<OrderDetailPage />);
    expect(await screen.findByText(/detalle de compra/i)).toBeInTheDocument();
    expect(screen.getByText(/GEMA-20260728-000001/)).toBeInTheDocument();
    expect(screen.getByText("ASUS TUF")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancelar orden/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ir al pago/i })).toBeInTheDocument();
  });
});
