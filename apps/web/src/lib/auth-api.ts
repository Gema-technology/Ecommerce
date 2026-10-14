export type User = {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string | null;
  is_active: boolean;
  email_verified: boolean;
  allow_cash_on_delivery: boolean;
  roles: string[];
};

export type RegisterPayload = {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  phone?: string;
};

export type LoginPayload = {
  email: string;
  password: string;
};

export type UpdateProfilePayload = {
  first_name?: string;
  last_name?: string;
  phone?: string | null;
};

export class ApiError extends Error {
  status: number;
  code?: string;
  details?: unknown;

  constructor(
    status: number,
    message: string,
    options?: { code?: string; details?: unknown },
  ) {
    super(message);
    this.status = status;
    this.code = options?.code;
    this.details = options?.details;
  }
}

export type PriceChangedItem = {
  product_id: string;
  product_name: string;
  previous_unit_price: string;
  current_unit_price: string;
  currency: string;
};

export type PriceChangedDetail = {
  code: "PRICE_CHANGED";
  message: string;
  items: PriceChangedItem[];
};

function parseErrorPayload(data: { detail?: unknown }): {
  message: string;
  code?: string;
  details?: unknown;
} {
  const detail = data.detail;
  if (typeof detail === "string") {
    return { message: detail };
  }
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.code === "string") {
      return {
        message:
          typeof obj.message === "string" ? obj.message : "Error en la solicitud",
        code: obj.code,
        details: obj,
      };
    }
  }
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return null;
      })
      .filter(Boolean);
    if (messages.length) return { message: messages.join("; ") };
  }
  return { message: "Error en la solicitud" };
}

async function parseError(response: Response): Promise<{
  message: string;
  code?: string;
  details?: unknown;
}> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    return parseErrorPayload(data);
  } catch {
    return { message: "Error en la solicitud" };
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(503, "API no disponible. Verifica que el backend esté en ejecución.");
  }

  if (!response.ok) {
    const parsed = await parseError(response);
    throw new ApiError(response.status, parsed.message, {
      code: parsed.code,
      details: parsed.details,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const authApi = {
  register(payload: RegisterPayload) {
    return request<User>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  login(payload: LoginPayload) {
    return request<User>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  logout() {
    return request<{ message: string }>("/api/v1/auth/logout", {
      method: "POST",
    });
  },
  me() {
    return request<User>("/api/v1/auth/me");
  },
  getProfile() {
    return request<User>("/api/v1/users/me");
  },
  updateProfile(payload: UpdateProfilePayload) {
    return request<User>("/api/v1/users/me", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
};

export function hasAnyRole(user: User | null, roles: string[]): boolean {
  if (!user?.roles?.length) return false;
  return roles.some((role) => user.roles.includes(role));
}

export function isAdmin(user: User | null): boolean {
  return hasAnyRole(user, ["ADMIN", "SUPER_ADMIN"]);
}
