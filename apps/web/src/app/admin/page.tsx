"use client";

import { useCallback, useEffect, useState } from "react";

import { AdminShell } from "@/components/admin/AdminShell";
import { KpiStrip } from "@/components/admin/dashboard/KpiStrip";
import { MoneyAtRiskPanel } from "@/components/admin/dashboard/MoneyAtRisk";
import { OpsBriefing } from "@/components/admin/dashboard/OpsBriefing";
import { OrdersByStatus } from "@/components/admin/dashboard/OrdersByStatus";
import { QuickLinks } from "@/components/admin/dashboard/QuickLinks";
import { RecentOrders } from "@/components/admin/dashboard/RecentOrders";
import { WorkQueue } from "@/components/admin/dashboard/WorkQueue";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/auth-api";
import { opsApi, type OpsPeriod, type OpsSummary } from "@/lib/ops-api";

const PERIODS: { value: OpsPeriod; label: string }[] = [
  { value: "today", label: "Hoy" },
  { value: "7d", label: "7 días" },
  { value: "30d", label: "30 días" },
];

export default function AdminHomePage() {
  const [period, setPeriod] = useState<OpsPeriod>("7d");
  const [summary, setSummary] = useState<OpsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (selected: OpsPeriod) => {
    setLoading(true);
    setError(null);
    try {
      setSummary(await opsApi.summary(selected));
    } catch (err) {
      setSummary(null);
      setError(err instanceof ApiError ? err.message : "No se pudo cargar el dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(period);
  }, [load, period]);

  return (
    <AdminShell title="Dashboard">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="max-w-xl text-sm text-secondary">
            Visión del negocio e indicadores del periodo. La bandeja operativa
            resume lo pendiente sin interrumpir el análisis.
          </p>
        </div>
        <div
          className="inline-flex rounded-lg border border-border bg-surface-secondary p-0.5"
          role="group"
          aria-label="Periodo del dashboard"
        >
          {PERIODS.map((option) => {
            const active = period === option.value;
            return (
              <button
                key={option.value}
                type="button"
                className={
                  active
                    ? "rounded-md bg-surface px-3 py-1.5 text-sm font-medium text-foreground"
                    : "rounded-md px-3 py-1.5 text-sm text-secondary hover:text-foreground"
                }
                aria-pressed={active}
                onClick={() => setPeriod(option.value)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {error ? (
        <p className="mb-4 text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}

      {loading && !summary ? (
        <DashboardSkeleton />
      ) : summary ? (
        <div className="space-y-8">
          {/* Primary: business performance */}
          <KpiStrip kpis={summary.kpis} />
          <OpsBriefing briefing={summary.briefing} />

          <div className="grid gap-4 lg:grid-cols-2">
            <OrdersByStatus ordersByStatus={summary.kpis.orders_by_status} />
            <MoneyAtRiskPanel data={summary.money_at_risk} />
          </div>

          {/* Activity + secondary operational inbox */}
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
            <RecentOrders orders={summary.recent_orders} />
            <WorkQueue items={summary.work_items} limit={5} />
          </div>

          <QuickLinks />
        </div>
      ) : null}
    </AdminShell>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-8" aria-busy="true" aria-label="Cargando dashboard">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-16 rounded-lg" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-72 rounded-xl" />
        <Skeleton className="h-72 rounded-xl" />
      </div>
      <div className="grid gap-4 lg:grid-cols-[1.55fr_1fr]">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    </div>
  );
}
