import type { Briefing } from "@/lib/ops-api";

type Props = {
  briefing: Briefing;
};

function statusDot(tone: Briefing["tone"]): string {
  switch (tone) {
    case "urgent":
      return "bg-error";
    case "watch":
      return "bg-warning";
    default:
      return "bg-success";
  }
}

function statusLabel(tone: Briefing["tone"]): string {
  switch (tone) {
    case "urgent":
      return "Atención requerida";
    case "watch":
      return "En seguimiento";
    default:
      return "Saludable";
  }
}

/** Compact insight line — supports the dashboard, does not dominate it. */
export function OpsBriefing({ briefing }: Props) {
  return (
    <div className="flex flex-wrap items-start gap-3 rounded-lg border border-border bg-surface-secondary/60 px-4 py-3">
      <span className="mt-1.5 flex items-center gap-2 shrink-0">
        <span
          className={`h-2 w-2 rounded-full ${statusDot(briefing.tone)}`}
          aria-hidden
        />
        <span className="text-xs font-medium uppercase tracking-wide text-secondary">
          {statusLabel(briefing.tone)}
        </span>
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{briefing.headline}</p>
        <p className="mt-0.5 text-sm leading-relaxed text-secondary">{briefing.detail}</p>
      </div>
    </div>
  );
}
