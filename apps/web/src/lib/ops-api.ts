import { ApiError } from "@/lib/auth-api";

export type OpsPeriod = "today" | "7d" | "30d";

export type AttentionSeverity = "critical" | "high" | "medium";

export type BriefingTone = "clear" | "watch" | "urgent";

export type WorkItemKind =
  | "confirm_payment"
  | "fulfill_order"
  | "aging_pending"
  | "fix_fiscal"
  | "expired_reservation"
  | "restock"
  | "failed_email";

export type OpsKpis = {
  period: OpsPeriod;
  period_start: string;
  orders_created: number;
  orders_paid: number;
  revenue_succeeded: string;
  avg_order_value: string;
  orders_by_status: Record<string, number>;
  quotes_open: number;
  orders_created_delta_pct: number | null;
  orders_paid_delta_pct: number | null;
  revenue_succeeded_delta_pct: number | null;
  avg_order_value_delta_pct: number | null;
};

export type MoneyAtRisk = {
  currency: string;
  awaiting_payment_confirm: string;
  fulfillment_backlog: string;
  aging_pending_payment: string;
  total: string;
};

export type AttentionItem = {
  key: string;
  label: string;
  count: number;
  severity: AttentionSeverity;
  href: string;
  oldest_age_hours: number | null;
};

export type WorkItem = {
  id: string;
  kind: WorkItemKind;
  severity: AttentionSeverity;
  score: number;
  title: string;
  reason: string;
  action_label: string;
  href: string;
  entity_label: string | null;
  amount: string | null;
  currency: string | null;
  age_hours: number | null;
};

export type Briefing = {
  headline: string;
  detail: string;
  tone: BriefingTone;
};

export type RecentOrderItem = {
  id: string;
  order_number: string;
  status: string;
  total: string;
  currency: string;
  customer_email: string | null;
  created_at: string;
};

export type OpsSummary = {
  briefing: Briefing;
  kpis: OpsKpis;
  money_at_risk: MoneyAtRisk;
  work_items: WorkItem[];
  attention: AttentionItem[];
  recent_orders: RecentOrderItem[];
};

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
    return "Error en la solicitud";
  } catch {
    return "Error en la solicitud";
  }
}

function apiBase(): string {
  if (typeof window === "undefined") {
    return process.env.API_ORIGIN?.replace(/\/$/, "") || "http://127.0.0.1:8000";
  }
  return "";
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
  return (await response.json()) as T;
}

export function formatMoney(amount: string | number, currency = "USD"): string {
  const value = typeof amount === "number" ? amount : Number(amount);
  if (Number.isNaN(value)) return String(amount);
  return new Intl.NumberFormat("es-EC", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatAgeHours(hours: number | null | undefined): string | null {
  if (hours == null) return null;
  if (hours < 1) return "< 1 h";
  if (hours < 48) return `${Math.round(hours)} h`;
  const days = Math.floor(hours / 24);
  return `${days} d`;
}

export function formatDeltaPct(delta: number | null | undefined): string | null {
  if (delta == null) return null;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(0)}%`;
}

export function attentionSeverityLabel(severity: AttentionSeverity): string {
  switch (severity) {
    case "critical":
      return "Crítica";
    case "high":
      return "Alta";
    case "medium":
      return "Media";
    default:
      return severity;
  }
}

export const opsApi = {
  summary(period: OpsPeriod = "7d") {
    const params = new URLSearchParams({ period });
    return request<OpsSummary>(`/api/v1/admin/ops/summary?${params}`);
  },
};
