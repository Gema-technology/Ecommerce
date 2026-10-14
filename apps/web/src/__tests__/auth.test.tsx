import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/app/login/page";
import RegisterPage from "@/app/register/page";
import AccountPage from "@/app/account/page";
import AdminPage from "@/app/admin/page";
import { AuthProvider } from "@/components/auth/AuthProvider";
import { CartProvider } from "@/components/cart/CartProvider";
import type { User } from "@/lib/auth-api";

const push = vi.fn();
const replace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace, prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
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

function mockFetchSequence(
  handlers: Array<(url: string, init?: RequestInit) => Response | Promise<Response>>,
) {
  let index = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const handler = handlers[index] ?? handlers[handlers.length - 1];
      index += 1;
      return handler(url, init);
    }),
  );
}

function renderWithAuth(ui: React.ReactElement) {
  return render(
    <AuthProvider>
      <CartProvider>{ui}</CartProvider>
    </AuthProvider>,
  );
}

beforeEach(() => {
  push.mockReset();
  replace.mockReset();
  vi.unstubAllGlobals();
});

describe("auth pages", () => {
  it("logs in successfully", async () => {
    const user = userEvent.setup();
    mockFetchSequence([
      () => new Response(null, { status: 401 }),
      () =>
        new Response(JSON.stringify(customer), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ]);

    renderWithAuth(<LoginPage />);
    await user.type(screen.getByLabelText(/correo/i), "customer@example.com");
    await user.type(screen.getByLabelText(/contraseña/i), "secure-password");
    await user.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/");
    });
  });

  it("registers successfully", async () => {
    const user = userEvent.setup();
    mockFetchSequence([
      () => new Response(null, { status: 401 }),
      () =>
        new Response(JSON.stringify(customer), {
          status: 201,
          headers: { "Content-Type": "application/json" },
        }),
    ]);

    renderWithAuth(<RegisterPage />);
    await user.type(screen.getByLabelText(/^nombre$/i), "John");
    await user.type(screen.getByLabelText(/apellido/i), "Doe");
    await user.type(screen.getByLabelText(/correo/i), "customer@example.com");
    await user.type(screen.getByLabelText(/contraseña/i), "secure-password");
    await user.click(screen.getByRole("button", { name: /registrarse/i }));

    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/account");
    });
  });

  it("logs out from account page", async () => {
    const user = userEvent.setup();
    mockFetchSequence([
      () =>
        new Response(JSON.stringify(customer), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      () =>
        new Response(JSON.stringify({ message: "Logged out" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ]);

    renderWithAuth(<AccountPage />);
    expect(
      await screen.findByRole("heading", { name: /mi cuenta/i }),
    ).toBeInTheDocument();
    await user.click(
      screen.getAllByRole("button", { name: /cerrar sesión/i }).at(-1)!,
    );
    await waitFor(() => {
      expect(push).toHaveBeenCalledWith("/");
    });
  });

  it("protects account page when unauthenticated", async () => {
    mockFetchSequence([() => new Response(null, { status: 401 })]);
    renderWithAuth(<AccountPage />);
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/login");
    });
  });

  it("denies admin page for customer via backend authorization", async () => {
    mockFetchSequence([
      () =>
        new Response(JSON.stringify(customer), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ]);

    renderWithAuth(<AdminPage />);
    expect(await screen.findByText(/acceso denegado/i)).toBeInTheDocument();
  });

  it("allows admin page for admin after backend check", async () => {
    mockFetchSequence([
      () =>
        new Response(JSON.stringify(admin), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      () =>
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
    ]);

    renderWithAuth(<AdminPage />);
    expect(
      await screen.findByText(/panel de administración/i),
    ).toBeInTheDocument();
  });
});
