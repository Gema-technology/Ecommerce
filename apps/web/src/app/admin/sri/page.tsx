"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import { ApiError } from "@/lib/auth-api";
import {
  sriApi,
  type SriConfig,
  type SriConfigUpdate,
  type TaxRegime,
} from "@/lib/sri-api";

export default function AdminSriPage() {
  const router = useRouter();
  const [form, setForm] = useState<SriConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await sriApi.getConfig();
        if (!cancelled) {
          setForm(data);
          setError(null);
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login?next=/admin/sri");
          return;
        }
        setError(
          err instanceof ApiError
            ? err.message
            : "No se pudo cargar la configuración SRI",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function patch<K extends keyof SriConfig>(key: K, value: SriConfig[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    setSaved(false);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setError(null);
    try {
      const payload: SriConfigUpdate = {
        tax_regime: form.tax_regime,
        ambiente: form.ambiente,
        establecimiento: form.establecimiento,
        punto_emision: form.punto_emision,
        dir_matriz: form.dir_matriz,
        dir_establecimiento: form.dir_establecimiento,
        obligado_contabilidad: form.obligado_contabilidad,
        contribuyente_especial: form.contribuyente_especial,
      };
      const updated = await sriApi.updateConfig(payload);
      setForm(updated);
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo guardar",
      );
    } finally {
      setSaving(false);
    }
  }

  async function onUpload(file: File | null) {
    if (!file) return;
    setUploading(true);
    setError(null);
    setVerifyMsg(null);
    try {
      const updated = await sriApi.uploadCert(file);
      setForm(updated);
      setVerifyMsg("Certificado subido. Verifica con SRI_CERT_PASSWORD en el servidor.");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "No se pudo subir el certificado",
      );
    } finally {
      setUploading(false);
    }
  }

  async function onVerify() {
    setVerifyMsg(null);
    try {
      const result = await sriApi.verifyCert();
      if (result.ok) {
        setVerifyMsg(
          `OK — ${result.subject ?? "certificado válido"}${
            result.not_valid_after
              ? ` (vence ${new Date(result.not_valid_after).toLocaleDateString("es-EC")})`
              : ""
          }`,
        );
      } else {
        setVerifyMsg(result.message ?? "No se pudo verificar");
      }
    } catch (err) {
      setVerifyMsg(
        err instanceof ApiError ? err.message : "Error al verificar",
      );
    }
  }

  return (
    <AdminShell title="Facturación SRI">
      {error ? (
        <p className="mb-4 text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p className="mb-4 text-sm text-secondary" role="status">
          Configuración SRI guardada.
        </p>
      ) : null}

      {loading || !form ? (
        <p className="text-sm text-secondary">Cargando…</p>
      ) : (
        <form onSubmit={(e) => void onSubmit(e)} className="space-y-6">
          <section className="gema-panel space-y-3 p-4">
            <h2 className="font-display text-base font-semibold">Emisor</h2>
            <p className="text-sm text-secondary">
              El RUC y razón social se toman de Configuración del negocio. Aquí
              defines régimen RIMPE, establecimiento y certificado.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">Régimen</span>
                <select
                  className="input-field w-full"
                  value={form.tax_regime}
                  onChange={(e) =>
                    patch("tax_regime", e.target.value as TaxRegime)
                  }
                >
                  <option value="RIMPE_NEGOCIO_POPULAR">
                    RIMPE — Negocio Popular
                  </option>
                  <option value="RIMPE_EMPRENDEDOR">RIMPE — Emprendedor</option>
                  <option value="GENERAL">Régimen General</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Ambiente SRI</span>
                <select
                  className="input-field w-full"
                  value={form.ambiente}
                  onChange={(e) =>
                    patch("ambiente", e.target.value as "1" | "2")
                  }
                >
                  <option value="1">1 — Pruebas</option>
                  <option value="2">2 — Producción</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">
                  Obligado a llevar contabilidad
                </span>
                <select
                  className="input-field w-full"
                  value={form.obligado_contabilidad}
                  onChange={(e) =>
                    patch(
                      "obligado_contabilidad",
                      e.target.value as "SI" | "NO",
                    )
                  }
                >
                  <option value="NO">NO</option>
                  <option value="SI">SI</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Establecimiento</span>
                <input
                  className="input-field w-full"
                  required
                  pattern="\d{3}"
                  maxLength={3}
                  value={form.establecimiento}
                  onChange={(e) => patch("establecimiento", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Punto de emisión</span>
                <input
                  className="input-field w-full"
                  required
                  pattern="\d{3}"
                  maxLength={3}
                  value={form.punto_emision}
                  onChange={(e) => patch("punto_emision", e.target.value)}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">Dirección matriz</span>
                <input
                  className="input-field w-full"
                  value={form.dir_matriz}
                  onChange={(e) => patch("dir_matriz", e.target.value)}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">
                  Dirección establecimiento
                </span>
                <input
                  className="input-field w-full"
                  value={form.dir_establecimiento}
                  onChange={(e) => patch("dir_establecimiento", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">
                  Contribuyente especial (opcional)
                </span>
                <input
                  className="input-field w-full"
                  value={form.contribuyente_especial}
                  onChange={(e) =>
                    patch("contribuyente_especial", e.target.value)
                  }
                />
              </label>
              <div className="text-sm text-secondary">
                <p>Secuencial nota de venta: {form.secuencial_nota_venta}</p>
                <p>Secuencial factura: {form.secuencial_factura}</p>
              </div>
            </div>
          </section>

          <section className="gema-panel space-y-3 p-4">
            <h2 className="font-display text-base font-semibold">
              Certificado electrónico (.p12)
            </h2>
            <p className="text-sm text-secondary">
              Sube el archivo .p12/.pfx. La contraseña va en la variable de
              entorno <code className="text-xs">SRI_CERT_PASSWORD</code> del
              API (nunca en la base de datos).
            </p>
            <p className="text-sm">
              Estado:{" "}
              {form.cert_stored
                ? `Cargado (${form.cert_filename || "emitter.p12"})`
                : "Sin certificado"}
              {form.cert_password_configured
                ? " · contraseña configurada en env"
                : " · falta SRI_CERT_PASSWORD"}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <label className="btn-ghost cursor-pointer">
                {uploading ? "Subiendo…" : "Subir .p12"}
                <input
                  type="file"
                  accept=".p12,.pfx"
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) =>
                    void onUpload(e.target.files?.[0] ?? null)
                  }
                />
              </label>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => void onVerify()}
              >
                Verificar firma
              </button>
            </div>
            {verifyMsg ? (
              <p className="text-sm text-secondary" role="status">
                {verifyMsg}
              </p>
            ) : null}
          </section>

          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Guardando…" : "Guardar configuración SRI"}
          </button>
        </form>
      )}
    </AdminShell>
  );
}
