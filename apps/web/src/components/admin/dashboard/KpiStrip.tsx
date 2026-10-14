import { formatDeltaPct, formatMoney, type OpsKpis } from "@/lib/ops-api";

type Props = {
  kpis: OpsKpis;
};

function Delta({ value }: { value: number | null }) {
  const label = formatDeltaPct(value);
  if (label == null) {
    return <span className="text-xs text-secondary">sin base anterior</span>;
  }
  const positive = (value ?? 0) > 0;
  const negative = (value ?? 0) < 0;
  const color = positive
    ? "text-success"
    : negative
      ? "text-error"
      : "text-secondary";
  return (
    <span className={`text-xs font-medium tabular-nums ${color}`}>
      {label} vs periodo anterior
    </span>
  );
}

export function KpiStrip({ kpis }: Props) {
  const items = [
    {
      label: "Pedidos creados",
      value: String(kpis.orders_created),
      delta: kpis.orders_created_delta_pct,
    },
    {
      label: "Pedidos cobrados",
      value: String(kpis.orders_paid),
      delta: kpis.orders_paid_delta_pct,
    },
    {
      label: "Ingresos confirmados",
      value: formatMoney(kpis.revenue_succeeded),
      delta: kpis.revenue_succeeded_delta_pct,
      emphasis: true,
    },
    {
      label: "Ticket promedio",
      value: formatMoney(kpis.avg_order_value),
      delta: kpis.avg_order_value_delta_pct,
    },
  ];

  return (
    <section>
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h2 className="font-display text-lg font-semibold">Indicadores</h2>
        {kpis.quotes_open > 0 ? (
          <p className="text-sm text-secondary">
            Cotizaciones abiertas:{" "}
            <span className="font-medium text-foreground">{kpis.quotes_open}</span>
          </p>
        ) : null}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {items.map((item) => (
          <div
            key={item.label}
            className={
              item.emphasis
                ? "gema-panel border-primary/25 p-4"
                : "gema-panel p-4"
            }
          >
            <p className="text-sm text-secondary">{item.label}</p>
            <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">
              {item.value}
            </p>
            <p className="mt-2">
              <Delta value={item.delta} />
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
