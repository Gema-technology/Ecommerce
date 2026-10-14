import { ApiError } from "@/lib/auth-api";

export type TaxRegime =
  | "RIMPE_NEGOCIO_POPULAR"
  | "RIMPE_EMPRENDEDOR"
  | "GENERAL";

export type SriConfig = {
  tax_regime: TaxRegime;
  ambiente: "1" | "2";
  establecimiento: string;
  punto_emision: string;
  dir_matriz: string;
  dir_establecimiento: string;
  obligado_contabilidad: "SI" | "NO";
  contribuyente_especial: string;
  secuencial_nota_venta: number;
  secuencial_factura: number;
  cert_filename: string;
  cert_stored: boolean;
  cert_password_configured: boolean;
  updated_at: string | null;
};

export type SriConfigUpdate = {
  tax_regime: TaxRegime;
  ambiente: "1" | "2";
  establecimiento: string;
  punto_emision: string;
  dir_matriz: string;
  dir_establecimiento: string;
  obligado_contabilidad: "SI" | "NO";
  contribuyente_especial: string;
};

export type FiscalDocType = "NOTA_VENTA" | "FACTURA";

export type BuyerIdType = "CEDULA" | "RUC" | "PASAPORTE" | "CONSUMIDOR_FINAL";

export type FiscalDocument = {
  id: string;
  order_id: string;
  doc_type: FiscalDocType | string;
  status: string;
  establishment: string;
  emission_point: string;
  sequential: number;
  document_number: string;
  access_key: string | null;
  buyer_id_type: string;
  buyer_id_number: string;
  buyer_name: string;
  buyer_email: string | null;
  buyer_address: string | null;
  currency: string;
  subtotal: string;
  tax_total: string;
  discount_total: string;
  shipping_total: string;
  total: string;
  tax_rate: string;
  authorization_number: string | null;
  authorized_at: string | null;
  sri_messages: string | null;
  has_pdf: boolean;
  has_xml: boolean;
  created_at: string;
  updated_at: string;
};

export type EmitFiscalPayload = {
  doc_type: FiscalDocType;
  buyer_id_type?: BuyerIdType | null;
  buyer_id_number?: string | null;
  buyer_name?: string | null;
  buyer_email?: string | null;
  buyer_address?: string | null;
  send_to_sri?: boolean;
};

async function parseError(response: Response): Promise<ApiError> {
  let message = response.statusText || "Request failed";
  try {
    const body = (await response.json()) as {
      detail?: string | { msg?: string }[];
    };
    if (typeof body.detail === "string") message = body.detail;
    else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
      message = body.detail[0].msg;
    }
  } catch {
    /* ignore */
  }
  return new ApiError(response.status, message);
}

async function request<T>(
  path: string,
  init?: RequestInit & { json?: unknown },
): Promise<T> {
  const headers = new Headers(init?.headers);
  let body = init?.body;
  if (init?.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const response = await fetch(path, {
    ...init,
    headers,
    body,
    credentials: "include",
  });
  if (!response.ok) throw await parseError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function fiscalStatusLabel(status: string): string {
  const map: Record<string, string> = {
    DRAFT: "Borrador",
    ISSUED: "Emitida",
    SIGNED: "Firmada",
    SENT: "Enviada al SRI",
    AUTHORIZED: "Autorizada",
    REJECTED: "Rechazada",
    CANCELLED: "Anulada",
  };
  return map[status] ?? status;
}

export const sriApi = {
  getConfig() {
    return request<SriConfig>("/api/v1/admin/sri/config");
  },
  updateConfig(payload: SriConfigUpdate) {
    return request<SriConfig>("/api/v1/admin/sri/config", {
      method: "PUT",
      json: payload,
    });
  },
  async uploadCert(file: File) {
    const form = new FormData();
    form.append("file", file);
    const response = await fetch("/api/v1/admin/sri/cert", {
      method: "POST",
      body: form,
      credentials: "include",
    });
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as SriConfig;
  },
  verifyCert() {
    return request<{
      ok: boolean;
      subject?: string | null;
      message?: string | null;
      not_valid_after?: string | null;
    }>("/api/v1/admin/sri/cert/verify", { method: "POST" });
  },
  listDocuments(page = 1, pageSize = 20) {
    return request<{
      items: FiscalDocument[];
      page: number;
      page_size: number;
      total: number;
      total_pages: number;
    }>(`/api/v1/admin/fiscal-documents?page=${page}&page_size=${pageSize}`);
  },
  listForOrder(orderId: string) {
    return request<FiscalDocument[]>(
      `/api/v1/admin/orders/${orderId}/fiscal-documents`,
    );
  },
  emit(orderId: string, payload: EmitFiscalPayload) {
    return request<FiscalDocument>(
      `/api/v1/admin/orders/${orderId}/fiscal-documents`,
      { method: "POST", json: payload },
    );
  },
  retryAuthorization(docId: string) {
    return request<FiscalDocument>(
      `/api/v1/admin/fiscal-documents/${docId}/retry-authorization`,
      { method: "POST" },
    );
  },
  pdfUrl(docId: string) {
    return `/api/v1/admin/fiscal-documents/${docId}/pdf`;
  },
  xmlUrl(docId: string) {
    return `/api/v1/admin/fiscal-documents/${docId}/xml`;
  },
};
