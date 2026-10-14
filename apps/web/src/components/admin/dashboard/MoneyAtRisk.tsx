import Link from "next/link";

import { formatMoney, type MoneyAtRisk as MoneyAtRiskData } from "@/lib/ops-api";

type Props = {
  data: MoneyAtRiskData;
};

export function MoneyAtRiskPanel({ data }: Props) {
  const rows = [
    {
      label: "Pagos por confirmar",
      value: data.awaiting_payment_confirm,
      href: "/admin/payments",
    },
    {
      label: "Pedidos por despachar",
      value: data.fulfillment_backlog,
      href: "/admin/orders",
    },
    {
      label: "Pendientes > 24 h",
      value: data.aging_pending_payment,
      href: "/admin/orders",
    },
  ];

  return (
    <section className="gema-panel flex h-full flex-col p-5">
      <h2 className="font-display text-lg font-semibold">Exposición operativa</h2>
      <p className="mt-1 text-sm text-secondary">
        Capital asociado a procesos abiertos
      </p>
      <p className="mt-4 text-3xl font-semibold tabular-nums tracking-tight">
        {formatMoney(data.total, data.currency)}
      </p>
      <p className="mt-1 text-xs text-secondary">Total en circulación / riesgo</p>
      <dl className="mt-5 flex-1 space-y-3 border-t border-border pt-4">
        {rows.map((row) => (
          <div key={row.label} className="flex items-baseline justify-between gap-3">
            <dt>
              <Link
                href={row.href}
                className="text-sm text-secondary transition hover:text-foreground"
              >
                {row.label}
              </Link>
            </dt>
            <dd className="text-sm font-medium tabular-nums">
              {formatMoney(row.value, data.currency)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
