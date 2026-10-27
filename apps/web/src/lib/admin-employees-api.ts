import { ApiError } from "@/lib/auth-api";

export type Employee = {
  id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  status: string;
  is_active: boolean;
  roles: string[];
  invited_at: string | null;
  accepted_at: string | null;
  invite_url?: string | null;
  email_sent?: boolean;
};

export type StaffRole = "ADMIN" | "SUPER_ADMIN";

export type InviteEmployeePayload = {
  email: string;
  first_name: string;
  last_name: string;
  role: StaffRole;
  job_title?: string | null;
};

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_ORIGIN?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  }
  return "";
}

async function parseError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      const messages = data.detail
        .map((item) => {
          if (typeof item === "string") return item;
          if (item && typeof item === "object" && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return null;
        })
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
  } catch {
    /* non-JSON */
  }
  if (response.status === 401) return "Debes iniciar sesión";
  if (response.status === 403) return "No tienes permisos";
  if (response.status >= 500) return "Error del servidor";
  return `Error en la solicitud (${response.status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(503, "API no disponible");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await parseError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type EmployeeListResponse = {
  items: Employee[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
};

export const adminEmployeesApi = {
  list(params?: {
    page?: number;
    page_size?: number;
    q?: string;
    status?: string;
  }) {
    const qs = new URLSearchParams();
    qs.set("page", String(params?.page ?? 1));
    qs.set("page_size", String(params?.page_size ?? 20));
    if (params?.q) qs.set("q", params.q);
    if (params?.status) qs.set("status", params.status);
    return request<EmployeeListResponse>(`/api/v1/admin/employees?${qs}`);
  },
  invite(payload: InviteEmployeePayload) {
    return request<Employee>("/api/v1/admin/employees/invite", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  setRole(employeeId: string, role: StaffRole) {
    return request<Employee>(`/api/v1/admin/employees/${employeeId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    });
  },
  setActive(employeeId: string, isActive: boolean) {
    return request<Employee>(`/api/v1/admin/employees/${employeeId}/active`, {
      method: "PATCH",
      body: JSON.stringify({ is_active: isActive }),
    });
  },
  resendInvite(employeeId: string) {
    return request<Employee>(`/api/v1/admin/employees/${employeeId}/resend-invite`, {
      method: "POST",
    });
  },
  resetPassword(employeeId: string) {
    return request<Employee>(
      `/api/v1/admin/employees/${employeeId}/reset-password`,
      { method: "POST" },
    );
  },
  acceptInvite(token: string, password: string) {
    return request<Employee>("/api/v1/auth/accept-invite", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
  },
};
