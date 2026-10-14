"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { lockBodyScroll, unlockBodyScroll } from "@/lib/body-scroll-lock";
import { useDismissArmed } from "@/lib/use-dismiss-armed";
import { cn } from "@/lib/cn";

export function Modal({
  open,
  title,
  children,
  onClose,
  className,
}: {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
  className?: string;
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
    <div className="gema-portal-layer flex items-end justify-center p-4 sm:items-center">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Cerrar"
        tabIndex={dismissArmed ? 0 : -1}
        onClick={dismissArmed ? () => onCloseRef.current() : undefined}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "gema-modal relative z-10 flex max-h-[min(92dvh,40rem)] w-full max-w-lg flex-col overflow-hidden p-5 sm:p-6",
          className,
        )}
      >
        <div className="mb-4 flex shrink-0 items-start justify-between gap-3">
          <h2 className="min-w-0 font-display text-lg font-semibold">{title}</h2>
          <button
            type="button"
            className="btn-ghost btn-icon shrink-0"
            aria-label="Cerrar"
            onClick={() => onCloseRef.current()}
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          {children}
        </div>
      </div>
    </div>,
    document.body,
  );
}
