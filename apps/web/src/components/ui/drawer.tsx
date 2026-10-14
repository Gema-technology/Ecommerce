"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { lockBodyScroll, unlockBodyScroll } from "@/lib/body-scroll-lock";
import { useDismissArmed } from "@/lib/use-dismiss-armed";
import { cn } from "@/lib/cn";

export function Drawer({
  open,
  title,
  children,
  onClose,
  side = "right",
  fullScreenOnMobile = false,
  /** When true, body is a flex column without its own scroll (child manages scroll/footer). */
  fill = false,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  side?: "right" | "left" | "bottom";
  fullScreenOnMobile?: boolean;
  fill?: boolean;
}) {
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
    return () => {
      window.removeEventListener("keydown", onKey);
      unlockBodyScroll();
    };
  }, [open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div className="gema-portal-layer" role="presentation">
      <button
        type="button"
        className="gema-backdrop-animate absolute inset-0 bg-black/40"
        aria-label="Cerrar panel"
        tabIndex={dismissArmed ? 0 : -1}
        onClick={dismissArmed ? () => onCloseRef.current() : undefined}
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "absolute z-10 flex max-h-[100dvh] flex-col border border-border bg-surface shadow-xl",
          "pb-[env(safe-area-inset-bottom)]",
          side === "right" &&
            cn(
              "gema-drawer-panel-right inset-y-0 right-0 w-full border-l",
              fullScreenOnMobile ? "max-w-full sm:max-w-md" : "max-w-md",
            ),
          side === "left" &&
            cn(
              "gema-drawer-panel-left inset-y-0 left-0 border-r",
              fullScreenOnMobile
                ? "w-[min(100%,24rem)] max-w-full sm:max-w-sm"
                : "w-full max-w-sm",
            ),
          side === "bottom" &&
            "animate-slide-up inset-x-0 bottom-0 max-h-[min(92vh,100dvh)] rounded-t-[var(--radius-md)] border-t",
        )}
      >
        <div className="flex shrink-0 items-center justify-between border-b border-border px-4 py-3.5 pt-[max(0.875rem,env(safe-area-inset-top))]">
          <h2 className="font-display text-lg font-semibold tracking-tight text-foreground">
            {title}
          </h2>
          <button
            type="button"
            className="btn-ghost btn-icon"
            aria-label="Cerrar"
            onClick={() => onCloseRef.current()}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div
          className={cn(
            "min-h-0 flex-1 p-4",
            fill
              ? "flex flex-col overflow-hidden"
              : "overflow-y-auto overscroll-contain [-webkit-overflow-scrolling:touch]",
          )}
        >
          {children}
        </div>
      </aside>
    </div>,
    document.body,
  );
}
