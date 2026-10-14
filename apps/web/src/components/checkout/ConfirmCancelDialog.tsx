"use client";

import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

import { lockBodyScroll, unlockBodyScroll } from "@/lib/body-scroll-lock";
import { useDismissArmed } from "@/lib/use-dismiss-armed";

type Props = {
  open: boolean;
  busy?: boolean;
  onClose: () => void;
  onConfirm: () => void;
};

export function ConfirmCancelDialog({
  open,
  busy,
  onClose,
  onConfirm,
}: Props) {
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
    <div
      className="gema-portal-layer flex items-end justify-center p-4 sm:items-center"
      role="presentation"
    >
      <button
        type="button"
        className="absolute inset-0 bg-navy/40 backdrop-blur-sm"
        aria-label="Cerrar"
        tabIndex={dismissArmed ? 0 : -1}
        onClick={dismissArmed ? () => onCloseRef.current() : undefined}
      />
      <div
        className="gema-panel-elevated relative z-10 max-h-[min(92dvh,28rem)] w-full max-w-md overflow-y-auto p-6"
        role="dialog"
        aria-modal="true"
        aria-labelledby="cancel-order-title"
      >
        <h2
          id="cancel-order-title"
          className="font-display text-xl font-semibold text-navy"
        >
          ¿Cancelar pedido?
        </h2>
        <p className="mt-2 text-sm text-secondary">
          Tu reserva de inventario será liberada y los productos volverán a
          estar disponibles para otros clientes.
        </p>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button type="button" className="btn-outline" onClick={onClose}>
            Volver
          </button>
          <button
            type="button"
            className="btn-danger"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Cancelando…" : "Cancelar pedido"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
