import { formatSpecKey } from "@/lib/catalog-api";

export function ProductSpecifications({
  specifications,
}: {
  specifications: Record<string, unknown>;
}) {
  const entries = Object.entries(specifications);
  if (!entries.length) {
    return <p className="text-sm text-secondary">Sin especificaciones</p>;
  }

  return (
    <dl className="overflow-hidden border border-border">
      {entries.map(([key, value], i) => (
        <div
          key={key}
          className={`grid grid-cols-1 sm:grid-cols-[14rem_1fr] ${
            i % 2 === 0 ? "bg-surface" : "bg-surface-highlight"
          } border-b border-border last:border-b-0`}
        >
          <dt className="min-w-0 break-words px-5 py-3.5 font-mono text-xs uppercase tracking-[0.06em] text-muted">
            {formatSpecKey(key)}
          </dt>
          <dd className="min-w-0 break-words px-5 py-3.5 font-mono text-sm text-secondary">
            {String(value)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
