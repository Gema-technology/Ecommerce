"use client";

import { Search, X } from "lucide-react";
import { FormEvent, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";

import { lockBodyScroll, unlockBodyScroll } from "@/lib/body-scroll-lock";
import { useDismissArmed } from "@/lib/use-dismiss-armed";
import { cn } from "@/lib/cn";

const POPULAR = ["Laptops", "Gaming", "RTX", "Monitores", "SSD"];

export function SearchOverlay({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const titleId = useId();
  const dismissArmed = useDismissArmed(open);
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    lockBodyScroll();
    const focusTimer = window.setTimeout(() => inputRef.current?.focus(), 0);
    return () => {
      window.removeEventListener("keydown", onKey);
      unlockBodyScroll();
      window.clearTimeout(focusTimer);
    };
  }, [open]);

  function submit(event?: FormEvent) {
    event?.preventDefault();
    const params = new URLSearchParams();
    if (q.trim()) params.set("search", q.trim());
    router.push(params.toString() ? `/products?${params}` : "/products");
    setQ("");
    onCloseRef.current();
  }

  function searchChip(term: string) {
    router.push(`/products?search=${encodeURIComponent(term)}`);
    onCloseRef.current();
  }

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="gema-portal-layer" role="presentation">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Cerrar búsqueda"
        tabIndex={dismissArmed ? 0 : -1}
        onClick={dismissArmed ? () => onCloseRef.current() : undefined}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={cn(
          "gema-modal absolute z-10 flex max-h-[min(92dvh,40rem)] w-full max-w-xl flex-col overflow-hidden",
          "inset-x-0 bottom-0 sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-[12vh] sm:-translate-x-1/2",
          "pb-[env(safe-area-inset-bottom)] sm:pb-0",
        )}
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => e.stopPropagation()}
      >
        <form
          onSubmit={submit}
          className="flex items-center gap-2 border-b border-border px-4 py-3"
        >
          <Search className="h-5 w-5 shrink-0 text-muted" aria-hidden />
          <h2 id={titleId} className="sr-only">
            Buscar productos
          </h2>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="min-w-0 flex-1 bg-transparent font-mono text-sm text-foreground outline-none placeholder:text-muted"
            placeholder="Buscar laptops, componentes, monitores…"
            aria-label="Buscar productos"
            enterKeyHint="search"
            autoCapitalize="off"
            autoCorrect="off"
          />
          <button
            type="button"
            className="btn-ghost btn-icon"
            aria-label="Cerrar"
            onClick={() => onCloseRef.current()}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </form>

        <div className="space-y-5 overflow-y-auto p-4 sm:p-5 [-webkit-overflow-scrolling:touch]">
          <div>
            <p className="gema-card-label">Populares</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {POPULAR.map((term) => (
                <button
                  key={term}
                  type="button"
                  className="gema-filter-chip"
                  onClick={() => searchChip(term)}
                >
                  {term}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
