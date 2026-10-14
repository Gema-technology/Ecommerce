"use client";

import { FormEvent, type ReactNode } from "react";

import { cn } from "@/lib/cn";

export function AdminFilterBar({
  children,
  onSubmit,
  onClear,
  className,
  actions,
}: {
  children: ReactNode;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onClear?: () => void;
  className?: string;
  /** Extra actions on the right (e.g. "Nuevo …" link). */
  actions?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "mb-6 flex flex-wrap items-end justify-between gap-4",
        className,
      )}
    >
      <form
        className="flex min-w-0 flex-wrap items-end gap-3"
        onSubmit={onSubmit}
      >
        {children}
        <button type="submit" className="btn-secondary">
          Filtrar
        </button>
        {onClear ? (
          <button type="button" className="btn-ghost" onClick={onClear}>
            Limpiar
          </button>
        ) : null}
      </form>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </div>
  );
}
