import { orderStatusLabel } from "@/lib/orders-api";

const STATUS_ORDER = [
  "PENDING_PAYMENT",
  "PAID",
  "PROCESSING",
  "SHIPPED",
  "DELIVERED",
  "CANCELLED",
] as const;

type Props = {
  ordersByStatus: Record<string, number>;
};

export function OrdersByStatus({ ordersByStatus }: Props) {
  const total = STATUS_ORDER.reduce(
    (sum, status) => sum + (ordersByStatus[status] ?? 0),
    0,
  );
  const max = Math.max(1, ...STATUS_ORDER.map((s) => ordersByStatus[s] ?? 0));

  return (
    <section className="gema-panel flex h-full flex-col p-5">
      <h2 className="font-display text-lg font-semibold">Embudo de pedidos</h2>
      <p className="mt-1 text-sm text-secondary">
        Distribución actual · {total} pedidos
      </p>
      <ul className="mt-5 flex-1 space-y-3.5">
        {STATUS_ORDER.map((status) => {
          const count = ordersByStatus[status] ?? 0;
          const width = `${Math.round((count / max) * 100)}%`;
          return (
            <li key={status}>
              <div className="mb-1.5 flex items-baseline justify-between gap-2 text-sm">
                <span className="text-secondary">{orderStatusLabel(status)}</span>
                <span className="font-medium tabular-nums">{count}</span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-secondary">
                <div
                  className="h-full rounded-full bg-primary/70"
                  style={{ width: count > 0 ? width : "0%" }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
