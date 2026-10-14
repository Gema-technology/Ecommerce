"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

export function AdminTable({
  columns,
  head,
  children,
  loading = false,
  error = null,
  emptyMessage = "Sin resultados.",
  isEmpty = false,
  footer,
  className,
  meta,
}: {
  /** Number of columns (for empty/loading colspan). */
  columns: number;
  /** Header row(s) inside `<thead>`. */
  head: ReactNode;
  /** Body rows (rendered only when not loading and not empty). */
  children: ReactNode;
  loading?: boolean;
  error?: string | null;
  emptyMessage?: string;
  isEmpty?: boolean;
  footer?: ReactNode;
  className?: string;
  /** Optional line above the table (e.g. "42 resultados"). */
  meta?: ReactNode;
}) {
  return (
    <div className={cn("space-y-4", className)}>
      {error ? (
        <p className="text-sm font-medium text-error" role="alert">
          {error}
        </p>
      ) : null}

      {meta ? (
        <p className="font-mono text-xs text-muted">{meta}</p>
      ) : null}

      <div className="gema-panel overflow-x-auto">
        <table className="gema-table">
          <thead>{head}</thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns} className="text-secondary">
                  Cargando…
                </td>
              </tr>
            ) : isEmpty ? (
              <tr>
                <td colSpan={columns} className="text-secondary">
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              children
            )}
          </tbody>
        </table>
      </div>

      {footer}
    </div>
  );
}
