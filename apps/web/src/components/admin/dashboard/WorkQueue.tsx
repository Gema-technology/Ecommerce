import Link from "next/link";
import { CheckCircle2, ChevronRight } from "lucide-react";

import {
  attentionSeverityLabel,
  formatAgeHours,
  formatMoney,
  type WorkItem,
} from "@/lib/ops-api";

type Props = {
  items: WorkItem[];
  /** Max items to show in the secondary inbox. */
  limit?: number;
};

function severityClass(severity: WorkItem["severity"]): string {
  switch (severity) {
    case "critical":
      return "gema-badge gema-badge-error";
    case "high":
      return "gema-badge gema-badge-warning";
    default:
      return "gema-badge gema-badge-muted";
  }
}

/** Secondary operational inbox — not the primary dashboard surface. */
export function WorkQueue({ items, limit = 5 }: Props) {
  const visible = items.slice(0, limit);
  const remaining = Math.max(items.length - visible.length, 0);

  return (
    <section className="gema-panel flex h-full flex-col overflow-hidden">
      <div className="border-b border-border px-5 py-4">
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="font-display text-lg font-semibold">Bandeja operativa</h2>
          {items.length > 0 ? (
            <span className="text-xs tabular-nums text-secondary">
              {items.length} pendiente{items.length === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
        <p className="mt-1 text-sm text-secondary">
          Acciones sugeridas según urgencia e impacto
        </p>
      </div>

      {visible.length === 0 ? (
        <div className="flex flex-1 items-start gap-3 px-5 py-6">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
          <div>
            <p className="text-sm font-medium text-foreground">Sin pendientes</p>
            <p className="mt-1 text-sm text-secondary">
              No hay ítems que requieran intervención ahora.
            </p>
          </div>
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {visible.map((item) => {
            const age = formatAgeHours(item.age_hours);
            return (
              <li key={item.id}>
                <Link
                  href={item.href}
                  className="flex items-start gap-3 px-5 py-3.5 transition hover:bg-surface-secondary"
                >
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className={severityClass(item.severity)}>
                        {attentionSeverityLabel(item.severity)}
                      </span>
                      {item.entity_label ? (
                        <span className="truncate text-xs text-secondary">
                          {item.entity_label}
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-1 block text-sm font-medium text-foreground">
                      {item.title}
                    </span>
                    <span className="mt-0.5 block text-xs text-secondary line-clamp-2">
                      {item.reason}
                    </span>
                    <span className="mt-1.5 flex flex-wrap gap-x-3 text-xs text-secondary">
                      {item.amount != null ? (
                        <span className="tabular-nums">
                          {formatMoney(item.amount, item.currency ?? "USD")}
                        </span>
                      ) : null}
                      {age ? <span>{age}</span> : null}
                    </span>
                  </span>
                  <ChevronRight
                    className="mt-1 h-4 w-4 shrink-0 text-secondary"
                    aria-hidden
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      )}

      {remaining > 0 ? (
        <p className="mt-auto border-t border-border px-5 py-3 text-xs text-secondary">
          +{remaining} más en el ranking operativo
        </p>
      ) : null}
    </section>
  );
}
