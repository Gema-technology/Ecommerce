import Link from "next/link";
import { Inbox } from "lucide-react";

export function EmptyState({
  title,
  description,
  actionHref = "/products",
  actionLabel = "Limpiar filtros",
}: {
  title: string;
  description?: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="gema-panel px-6 py-14 text-center animate-fade-in">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center border border-border bg-surface-secondary text-primary">
        <Inbox className="gema-card-icon h-5 w-5" aria-hidden />
      </div>
      <h2 className="font-display text-lg font-semibold text-foreground">{title}</h2>
      {description ? (
        <p className="mx-auto mt-2 max-w-md text-sm text-secondary">{description}</p>
      ) : null}
      <Link href={actionHref} className="btn-primary mt-6 inline-flex">
        {actionLabel}
      </Link>
    </div>
  );
}
