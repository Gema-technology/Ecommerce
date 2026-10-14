import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import OrderPaymentPage from "@/app/orders/[order_number]/payment/page";
import PaymentSuccessPage from "@/app/payment/success/page";
import PaymentFailedPage from "@/app/payment/failed/page";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { CartProvider } from "@/components/cart/CartProvider";
import type { User } from "@/lib/auth-api";

const push = vi.fn();
let searchParams = new URLSearchParams("payment_id=pay-1");

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/orders/GEMA-20260728-000001/payment",
  useParams: () => ({ order_number: "GEMA-20260728-000001" }),
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

const order = {
  id: "ord-1",
  order_number: "GEMA-20260728-000001",
  status: "PENDING_PAYMENT",
  currency: "USD",
  subtotal: "1199.9900",
  tax_total: "0.0000",
  shipping_total: "0.0000",
  discount_total: "0.0000",
  total: "1199.9900",
  created_at: "2026-07-28T10:00:00Z",
  updated_at: "2026-07-28T10:00:00Z",
  items: [
    {
      id: "oi-1",
      product_id: "p1",
      product_name_snapshot: "ASUS TUF",
      sku_snapshot: "LAP-1",
      unit_price: "1199.9900",
      quantity: 1,
      line_total: "1199.9900",
      created_at: "2026-07-28T10:00:00Z",
    },
  ],
};

const paymentPending = {
  id: "pay-1",
  payment_id: "pay-1",
  order_id: "ord-1",
  order_number: "GEMA-20260728-000001",
  provider: "manual",
  provider_payment_id: "manual_pay-1",
  method: "CARD",
  status: "PROCESSING",
  amount: "1199.9900",
  currency: "USD",
  metadata: {},
  created_at: "2026-07-28T10:01:00Z",
  updated_at: "2026-07-28T10:01:00Z",
  paid_at: null,
  client_action: { type: "manual_pending" },
};

const paymentSucceeded = {
  ...paymentPending,
  status: "SUCCEEDED",
  paid_at: "2026-07-28T10:02:00Z",
};

const paymentFailed = {
  ...paymentPending,
  status: "FAILED",
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
  searchParams = new URLSearchParams("payment_id=pay-1");
  vi.unstubAllGlobals();
});

describe("payment frontend", () => {
  it("shows order summary and starts payment", async () => {
    let paymentItems: typeof paymentPending[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.includes("/auth/me")) return json(customer);
      if (url.includes("/cart")) {
        return json({
          id: "c1",
          status: "ACTIVE",
          items: [],
          subtotal: "0",
          currency: "USD",
          item_count: 0,
        });
      }
      if (url.includes("/orders/by-number/")) return json(order);
      if (url.includes("/payment") && method === "POST" && url.includes("/orders/")) {
        paymentItems = [paymentPending];
        return json(paymentPending);
      }
      if (url.includes("/payments") && method === "GET" && url.includes("/orders/")) {
        return json({ items: paymentItems });
      }
      return json({});
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp(<OrderPaymentPage />);
    expect(await screen.findByRole("heading", { name: /pago de orden/i })).toBeInTheDocument();
    expect(screen.getByText("ASUS TUF")).toBeInTheDocument();
    expect(screen.getByText(/GEMA-20260728-000001/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /iniciar pago/i }));
    expect(await screen.findByText(/intentos de pago/i)).toBeInTheDocument();
    expect(screen.getByText(/procesando/i)).toBeInTheDocument();
  });

  it("success page verifies backend status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) {
          return json({
            id: "c1",
            status: "ACTIVE",
            items: [],
            subtotal: "0",
            currency: "USD",
            item_count: 0,
          });
        }
        if (url.includes("/payments/pay-1")) return json(paymentSucceeded);
        return json({});
      }),
    );

    renderApp(<PaymentSuccessPage />);
    expect(
      await screen.findByRole("heading", { name: /pago confirmado/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Exitoso/i)).toBeInTheDocument();
  });

  it("success page shows not confirmed when backend says failed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) {
          return json({
            id: "c1",
            status: "ACTIVE",
            items: [],
            subtotal: "0",
            currency: "USD",
            item_count: 0,
          });
        }
        if (url.includes("/payments/pay-1")) return json(paymentFailed);
        return json({});
      }),
    );

    renderApp(<PaymentSuccessPage />);
    expect(
      await screen.findByRole("heading", { name: /pago no confirmado/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /intentar nuevamente/i })).toBeInTheDocument();
  });

  it("failure page allows retry", async () => {
    searchParams = new URLSearchParams(
      "payment_id=pay-1&order_number=GEMA-20260728-000001",
    );
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes("/auth/me")) return json(customer);
        if (url.includes("/cart")) {
          return json({
            id: "c1",
            status: "ACTIVE",
            items: [],
            subtotal: "0",
            currency: "USD",
            item_count: 0,
          });
        }
        if (url.includes("/payments/pay-1")) return json(paymentFailed);
        return json({});
      }),
    );

    renderApp(<PaymentFailedPage />);
    expect(
      await screen.findByRole("heading", { name: /pago no completado/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /intentar nuevamente/i })).toHaveAttribute(
      "href",
      "/orders/GEMA-20260728-000001/payment",
    );
    expect(
      screen.getByRole("link", { name: /ver orden \/ cancelar/i }),
    ).toHaveAttribute("href", "/orders/GEMA-20260728-000001");
    expect(
      screen.getByText(/stock reservado se liberó/i),
    ).toBeInTheDocument();
  });
});
