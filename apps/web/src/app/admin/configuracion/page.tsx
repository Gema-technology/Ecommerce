"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import { ApiError } from "@/lib/auth-api";
import {
  storeConfigApi,
  type StoreConfig,
  type StoreConfigUpdate,
} from "@/lib/store-config-api";

type ProvinceRow = { province: string; rate: string };

function ratesToRows(rates: Record<string, string>): ProvinceRow[] {
  const entries = Object.entries(rates);
  if (!entries.length) return [{ province: "", rate: "" }];
  return entries.map(([province, rate]) => ({ province, rate: String(rate) }));
}

function rowsToRates(rows: ProvinceRow[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of rows) {
    const name = row.province.trim();
    if (!name || !row.rate.trim()) continue;
    out[name] = row.rate.trim();
  }
  return out;
}

export default function AdminConfiguracionPage() {
  const router = useRouter();
  const [form, setForm] = useState<StoreConfig | null>(null);
  const [provinces, setProvinces] = useState<ProvinceRow[]>([
    { province: "", rate: "" },
  ]);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await storeConfigApi.get();
        if (cancelled) return;
        setForm(data);
        setProvinces(ratesToRows(data.shipping_province_rates ?? {}));
        setError(null);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          router.replace("/login?next=/admin/configuracion");
          return;
        }
        setError(
          err instanceof ApiError
            ? err.message
            : "No se pudo cargar la configuración",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function patch<K extends keyof StoreConfig>(key: K, value: StoreConfig[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    setSaved(false);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    const payload: StoreConfigUpdate = {
      business_name: form.business_name,
      business_ruc: form.business_ruc,
      business_phone: form.business_phone,
      business_address: form.business_address,
      business_email: form.business_email,
      bank_name: form.bank_name,
      bank_account_type:
        form.bank_account_type === "Corriente" ? "Corriente" : "Ahorros",
      bank_account_number: form.bank_account_number,
      bank_account_holder: form.bank_account_holder,
      bank_account_id: form.bank_account_id,
      bank_transfer_instructions: form.bank_transfer_instructions,
      shipping_enabled: form.shipping_enabled,
      shipping_flat_rate: form.shipping_flat_rate,
      shipping_free_threshold: form.shipping_free_threshold || null,
      shipping_province_rates: rowsToRates(provinces),
    };
    try {
      const updated = await storeConfigApi.update(payload);
      setForm(updated);
      setProvinces(ratesToRows(updated.shipping_province_rates ?? {}));
      setSaved(true);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "No se pudo guardar la configuración",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminShell title="Configuración">
      <p className="mb-6 max-w-2xl text-sm text-secondary">
        Datos del negocio, transferencia bancaria y envío. Los secretos de
        PayPhone siguen en el servidor (.env).
      </p>

      {error ? (
        <p className="mb-4 text-sm text-error" role="alert">
          {error}
        </p>
      ) : null}
      {saved ? (
        <p className="mb-4 text-sm text-secondary" role="status">
          Configuración guardada.
        </p>
      ) : null}

      {loading || !form ? (
        <p className="text-sm text-secondary">Cargando…</p>
      ) : (
        <form onSubmit={(e) => void onSubmit(e)} className="space-y-6">
          <section className="gema-panel space-y-3 p-4">
            <h2 className="font-display text-base font-semibold">
              Datos del negocio
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">Nombre</span>
                <input
                  className="input-field w-full"
                  required
                  value={form.business_name}
                  onChange={(e) => patch("business_name", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">RUC</span>
                <input
                  className="input-field w-full"
                  value={form.business_ruc}
                  onChange={(e) => patch("business_ruc", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Teléfono</span>
                <input
                  className="input-field w-full"
                  value={form.business_phone}
                  onChange={(e) => patch("business_phone", e.target.value)}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">Dirección</span>
                <input
                  className="input-field w-full"
                  value={form.business_address}
                  onChange={(e) => patch("business_address", e.target.value)}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">Correo</span>
                <input
                  className="input-field w-full"
                  type="email"
                  value={form.business_email}
                  onChange={(e) => patch("business_email", e.target.value)}
                />
              </label>
            </div>
          </section>

          <section className="gema-panel space-y-3 p-4">
            <h2 className="font-display text-base font-semibold">
              Transferencia bancaria
            </h2>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Banco</span>
                <input
                  className="input-field w-full"
                  value={form.bank_name}
                  onChange={(e) => patch("bank_name", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Tipo de cuenta</span>
                <select
                  className="input-field w-full"
                  value={form.bank_account_type}
                  onChange={(e) =>
                    patch("bank_account_type", e.target.value)
                  }
                >
                  <option value="Ahorros">Ahorros</option>
                  <option value="Corriente">Corriente</option>
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Número de cuenta</span>
                <input
                  className="input-field w-full"
                  value={form.bank_account_number}
                  onChange={(e) => patch("bank_account_number", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Titular</span>
                <input
                  className="input-field w-full"
                  value={form.bank_account_holder}
                  onChange={(e) => patch("bank_account_holder", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">RUC / CI titular</span>
                <input
                  className="input-field w-full"
                  value={form.bank_account_id}
                  onChange={(e) => patch("bank_account_id", e.target.value)}
                />
              </label>
              <label className="block text-sm sm:col-span-2">
                <span className="mb-1 block text-secondary">Instrucciones</span>
                <textarea
                  className="input-field w-full min-h-20"
                  value={form.bank_transfer_instructions}
                  onChange={(e) =>
                    patch("bank_transfer_instructions", e.target.value)
                  }
                />
              </label>
            </div>
          </section>

          <section className="gema-panel space-y-3 p-4">
            <h2 className="font-display text-base font-semibold">Envío</h2>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.shipping_enabled}
                onChange={(e) => patch("shipping_enabled", e.target.checked)}
              />
              Envío habilitado
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">Tarifa fija (USD)</span>
                <input
                  className="input-field w-full"
                  type="number"
                  min="0"
                  step="0.01"
                  required
                  value={form.shipping_flat_rate}
                  onChange={(e) => patch("shipping_flat_rate", e.target.value)}
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-secondary">
                  Envío gratis desde (USD)
                </span>
                <input
                  className="input-field w-full"
                  type="number"
                  min="0"
                  step="0.01"
                  value={form.shipping_free_threshold ?? ""}
                  onChange={(e) =>
                    patch(
                      "shipping_free_threshold",
                      e.target.value ? e.target.value : null,
                    )
                  }
                />
              </label>
            </div>
            <div className="space-y-2">
              <p className="text-sm text-secondary">
                Tarifas por provincia (opcional)
              </p>
              {provinces.map((row, index) => (
                <div key={index} className="flex flex-wrap gap-2">
                  <input
                    className="input-field min-w-[10rem] flex-1"
                    placeholder="Provincia"
                    value={row.province}
                    onChange={(e) => {
                      const next = [...provinces];
                      next[index] = { ...row, province: e.target.value };
                      setProvinces(next);
                      setSaved(false);
                    }}
                  />
                  <input
                    className="input-field w-28"
                    placeholder="USD"
                    type="number"
                    min="0"
                    step="0.01"
                    value={row.rate}
                    onChange={(e) => {
                      const next = [...provinces];
                      next[index] = { ...row, rate: e.target.value };
                      setProvinces(next);
                      setSaved(false);
                    }}
                  />
                  <button
                    type="button"
                    className="btn-ghost"
                    onClick={() => {
                      setProvinces(provinces.filter((_, i) => i !== index));
                      setSaved(false);
                    }}
                  >
                    Quitar
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="btn-ghost"
                onClick={() =>
                  setProvinces([...provinces, { province: "", rate: "" }])
                }
              >
                + Provincia
              </button>
            </div>
          </section>

          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Guardando…" : "Guardar configuración"}
          </button>
        </form>
      )}
    </AdminShell>
  );
}
