import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CartPage from "@/app/cart/page";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { CartProvider } from "@/components/cart/CartProvider";
import { AddToCartButton } from "@/components/cart/AddToCartButton";
import { StoreHeader } from "@/components/layout/StoreHeader";
import type { User } from "@/lib/auth-api";
import type { Cart } from "@/lib/cart-api";

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

const emptyCart: Cart = {
  id: "c1",
  status: "ACTIVE",
  items: [],
  subtotal: "0.0000",
  currency: "USD",
  item_count: 0,
};

const filledCart: Cart = {
  id: "c1",
  status: "ACTIVE",
  items: [
    {
      id: "i1",
      quantity: 2,
      line_total: "200.0000",
      available: true,
      product: {
        id: "p1",
        name: "ASUS TUF",
        slug: "asus-tuf",
        sku: "LAP-1",
        image: "/a.jpg",
        price: { amount: "100.0000", currency: "USD" },
        is_active: true,
        availability: "IN_STOCK",
      },
    },
  ],
  subtotal: "200.0000",
  currency: "USD",
  item_count: 2,
};

const unavailableCart: Cart = {
  ...filledCart,
  items: [
    {
      ...filledCart.items[0],
      available: false,
      line_total: null,
      product: {
        ...filledCart.items[0].product,
        is_active: false,
      },
    },
  ],
  subtotal: "0.0000",
  item_count: 2,
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderCart(ui: React.ReactElement) {
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

describe("cart frontend", () => {
  it("shows empty cart state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) return json(emptyCart);
        return new Response(null, { status: 404 });
      }),
    );

    renderCart(<CartPage />);
    expect(await screen.findByText(/tu carrito está vacío/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ver productos/i })).toHaveAttribute(
      "href",
      "/products",
    );
  });

  it("renders items, subtotal and quantity controls", async () => {
    const user = userEvent.setup();
    let cartState = structuredClone(filledCart);
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart/items/") && method === "PATCH") {
          const body = JSON.parse(String(init?.body)) as { quantity: number };
          cartState = {
            ...cartState,
            items: cartState.items.map((i) =>
              i.id === "i1"
                ? {
                    ...i,
                    quantity: body.quantity,
                    line_total: String(100 * body.quantity) + ".0000",
                  }
                : i,
            ),
            item_count: body.quantity,
            subtotal: String(100 * body.quantity) + ".0000",
          };
          return json(cartState);
        }
        if (url.includes("/cart")) return json(cartState);
        return new Response(null, { status: 404 });
      }),
    );

    renderCart(<CartPage />);
    expect(await screen.findByText("ASUS TUF")).toBeInTheDocument();
    expect(screen.getAllByText(/subtotal/i).length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: /aumentar cantidad/i }));
    await waitFor(() => {
      expect(screen.getByLabelText(/cantidad 3/i)).toBeInTheDocument();
    });
  });

  it("decreases quantity and then removes the product", async () => {
    const user = userEvent.setup();
    let cartState = structuredClone(filledCart);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/auth/me")) return json(customer);
      if (url.includes("/cart/items/") && method === "PATCH") {
        const body = JSON.parse(String(init?.body)) as { quantity: number };
        expect(body.quantity).toBe(1);
        cartState = {
          ...cartState,
          items: cartState.items.map((i) =>
            i.id === "i1"
              ? {
                  ...i,
                  quantity: body.quantity,
                  line_total: `${100 * body.quantity}.0000`,
                }
              : i,
          ),
          item_count: body.quantity,
          subtotal: `${100 * body.quantity}.0000`,
        };
        return json(cartState);
      }
      if (url.includes("/cart/items/") && method === "DELETE") {
        cartState = structuredClone(emptyCart);
        return json(cartState);
      }
      if (url.includes("/cart")) return json(cartState);
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderCart(<CartPage />);
    expect(await screen.findByText("ASUS TUF")).toBeInTheDocument();
    expect(screen.getByLabelText(/cantidad 2/i)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /disminuir cantidad/i }));
    await waitFor(() => {
      expect(screen.getByLabelText(/cantidad 1/i)).toBeInTheDocument();
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/cart/items/i1"),
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({ quantity: 1 }),
      }),
    );

    await user.click(screen.getByRole("button", { name: /eliminar/i }));
    expect(await screen.findByText(/tu carrito está vacío/i)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/cart/items/i1"),
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("removes item", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart/items/") && method === "DELETE") {
          return json(emptyCart);
        }
        if (url.includes("/cart")) return json(filledCart);
        return new Response(null, { status: 404 });
      }),
    );

    renderCart(<CartPage />);
    expect(await screen.findByText("ASUS TUF")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /eliminar/i }));
    expect(await screen.findByText(/tu carrito está vacío/i)).toBeInTheDocument();
  });

  it("shows unavailable product state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) return json(unavailableCart);
        return new Response(null, { status: 404 });
      }),
    );

    renderCart(<CartPage />);
    expect(await screen.findByText(/no disponible actualmente/i)).toBeInTheDocument();
  });

  it("header shows cart counter", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) return json(filledCart);
        return new Response(null, { status: 404 });
      }),
    );

    renderCart(<StoreHeader />);
    expect(
      await screen.findByRole("button", { name: /abrir carrito \(2\)/i }),
    ).toBeInTheDocument();
  });

  it("add to cart button posts item", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart/items") && method === "POST") {
          return json(filledCart);
        }
        if (url.includes("/cart")) return json(emptyCart);
        return new Response(null, { status: 404 });
      }),
    );

    renderCart(<AddToCartButton productId="p1" />);
    await user.click(await screen.findByRole("button", { name: /agregar al carrito/i }));
    expect(await screen.findByText(/agregado/i)).toBeInTheDocument();
  });
});
