"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

export function Pagination({
  page,
  totalPages,
  basePath = "/products",
  total,
  className,
}: {
  page: number;
  totalPages: number;
  basePath?: string;
  /** Optional total item count shown above controls. */
  total?: number;
  className?: string;
}) {
  const params = useSearchParams();

  if (totalPages <= 1) {
    if (total == null) return null;
    return (
      <p
        className={`mt-4 text-center font-mono text-xs text-muted ${className ?? ""}`}
      >
        {total} resultado{total === 1 ? "" : "s"}
      </p>
    );
  }

  function hrefFor(p: number) {
    const next = new URLSearchParams(params.toString());
    if (p <= 1) next.delete("page");
    else next.set("page", String(p));
    const qs = next.toString();
    return qs ? `${basePath}?${qs}` : basePath;
  }

  const windowStart = Math.max(1, page - 2);
  const windowEnd = Math.min(totalPages, page + 2);
  const pages = [];
  for (let i = windowStart; i <= windowEnd; i += 1) pages.push(i);

  return (
    <div className={className}>
      {total != null ? (
        <p className="mb-3 text-center font-mono text-xs text-muted">
          Página {page} de {totalPages} · {total} resultado
          {total === 1 ? "" : "s"}
        </p>
      ) : null}
      <nav
        className="mt-4 flex flex-wrap items-center justify-center gap-2"
        aria-label="Paginación"
      >
      <Link
        href={hrefFor(Math.max(1, page - 1))}
        className={`btn-ghost btn-sm ${page <= 1 ? "pointer-events-none opacity-40" : ""}`}
        aria-disabled={page <= 1}
      >
        Anterior
      </Link>
      {windowStart > 1 ? (
        <>
          <Link href={hrefFor(1)} className="btn-ghost btn-sm btn-icon">
            1
          </Link>
          {windowStart > 2 ? <span className="text-muted">…</span> : null}
        </>
      ) : null}
      {pages.map((p) => (
        <Link
          key={p}
          href={hrefFor(p)}
          className={
            p === page ? "btn-primary btn-sm btn-icon" : "btn-ghost btn-sm btn-icon"
          }
          aria-current={p === page ? "page" : undefined}
        >
          {p}
        </Link>
      ))}
      {windowEnd < totalPages ? (
        <>
          {windowEnd < totalPages - 1 ? (
            <span className="text-muted">…</span>
          ) : null}
          <Link href={hrefFor(totalPages)} className="btn-ghost btn-sm btn-icon">
            {totalPages}
          </Link>
        </>
      ) : null}
      <Link
        href={hrefFor(Math.min(totalPages, page + 1))}
        className={`btn-ghost btn-sm ${page >= totalPages ? "pointer-events-none opacity-40" : ""}`}
        aria-disabled={page >= totalPages}
      >
        Siguiente
      </Link>
      </nav>
    </div>
  );
}
