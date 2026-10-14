import Link from "next/link";
import { AlertTriangle, CheckCircle2, ChevronRight } from "lucide-react";

import {
  attentionSeverityLabel,
  formatAgeHours,
  type AttentionItem,
} from "@/lib/ops-api";

type Props = {
  items: AttentionItem[];
};

function severityClass(severity: AttentionItem["severity"]): string {
  switch (severity) {
    case "critical":
      return "gema-badge gema-badge-error";
    case "high":
      return "gema-badge gema-badge-warning";
    default:
      return "gema-badge gema-badge-muted";
  }
}

export function AttentionQueue({ items }: Props) {
  if (items.length === 0) {
    return (
      <section className="gema-panel p-6">
        <div className="flex items-start gap-3">
          <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" aria-hidden />
          <div>
            <h2 className="font-display text-lg font-semibold">Por categoría</h2>
            <p className="mt-1 text-sm text-secondary">Sin categorías con backlog.</p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle className="h-5 w-5 text-warning" aria-hidden />
        <h2 className="font-display text-lg font-semibold">Por categoría</h2>
      </div>
      <div className="gema-panel divide-y divide-border overflow-hidden">
        {items.map((item) => {
          const age = formatAgeHours(item.oldest_age_hours);
          return (
            <Link
              key={item.key}
              href={item.href}
              className="flex items-center gap-3 px-4 py-3 transition hover:bg-surface-secondary"
            >
              <span className={`${severityClass(item.severity)} shrink-0`}>
                {attentionSeverityLabel(item.severity)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-foreground">{item.label}</span>
                <span className="text-sm text-secondary">
                  {item.count} {item.count === 1 ? "caso" : "casos"}
                  {age ? ` · el más antiguo: ${age}` : null}
                </span>
              </span>
              <ChevronRight className="h-4 w-4 shrink-0 text-secondary" aria-hidden />
            </Link>
          );
        })}
      </div>
    </section>
  );
}
