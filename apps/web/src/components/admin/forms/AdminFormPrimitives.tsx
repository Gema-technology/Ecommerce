"use client";

import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { lockBodyScroll, unlockBodyScroll } from "@/lib/body-scroll-lock";
import { useDismissArmed } from "@/lib/use-dismiss-armed";
import { cn } from "@/lib/cn";

/** Reusable shell for all admin create/edit forms (list + modal pattern). */
export function FormModal({
  open,
  title,
  subtitle,
  children,
  footer,
  onClose,
  size = "md",
}: {
  open: boolean;
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
  size?: "md" | "lg";
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
    <div
      className="admin-form-modal gema-portal-layer flex items-end justify-center p-4 sm:items-center"
      role="presentation"
    >
      <button
        type="button"
        className="gema-backdrop-animate absolute inset-0 bg-black/50 backdrop-blur-[2px]"
        aria-label="Cerrar"
        tabIndex={dismissArmed ? 0 : -1}
        onClick={dismissArmed ? () => onCloseRef.current() : undefined}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "admin-form-modal-panel gema-modal relative z-10 flex w-full flex-col overflow-hidden",
          size === "lg" ? "max-w-2xl" : "max-w-lg",
          "max-h-[min(92dvh,720px)]",
        )}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border px-5 py-4 sm:px-6 sm:py-5">
          <div className="min-w-0 pr-2">
            <h2 className="font-display text-lg font-bold tracking-tight text-foreground">
              {title}
            </h2>
            {subtitle ? (
              <p className="admin-form-modal-sub truncate">{subtitle}</p>
            ) : null}
          </div>
          <button
            type="button"
            className="btn-ghost btn-icon btn-sm shrink-0"
            aria-label="Cerrar"
            onClick={() => onCloseRef.current()}
          >
            <X className="h-3.5 w-3.5" aria-hidden />
          </button>
        </div>
        <div className="admin-form-modal-body min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-5 sm:px-6 [-webkit-overflow-scrolling:touch]">
          {children}
        </div>
        {footer ? (
          <div className="admin-form-modal-foot shrink-0 border-t border-border px-5 py-4 sm:px-6">
            {footer}
          </div>
        ) : null}
      </div>
    </div>,
    document.body,
  );
}

/** @deprecated Use FormModal */
export const AdminFormModal = FormModal;

/** @deprecated Use FormModal */
export const AdminFormDrawer = FormModal;

/** Cancel + submit actions for forms hosted inside FormModal (`form` attribute). */
export function FormModalActions({
  formId,
  submitLabel,
  cancelLabel = "Cancelar",
  saving = false,
  onCancel,
}: {
  formId: string;
  submitLabel: string;
  cancelLabel?: string;
  saving?: boolean;
  onCancel: () => void;
}) {
  return (
    <>
      <button type="button" className="btn-ghost" onClick={onCancel} disabled={saving}>
        {cancelLabel}
      </button>
      <button type="submit" form={formId} className="btn-primary" disabled={saving}>
        {saving ? "Guardando…" : submitLabel}
      </button>
    </>
  );
}

export function FormSection({
  label,
  children,
  className,
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("admin-form-section", className)}>
      <span className="admin-form-section-label">{label}</span>
      {children}
    </section>
  );
}

export function FieldRow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("admin-form-row", className)}>{children}</div>;
}

export function PriceInput({
  id,
  value,
  onChange,
  required,
  placeholder = "0.00",
  disabled,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  placeholder?: string;
  disabled?: boolean;
}) {
  return (
    <div className="price-input-wrap">
      <span className="price-prefix" aria-hidden>
        USD
      </span>
      <input
        id={id}
        type="number"
        step="0.01"
        min="0"
        required={required}
        disabled={disabled}
        placeholder={placeholder}
        className="input-field price-input-field"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

export function StatusToggle({
  label,
  sublabel,
  checked,
  onChange,
  id,
}: {
  label: string;
  sublabel?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  id?: string;
}) {
  const inputId = id ?? label.replace(/\s+/g, "-").toLowerCase();
  return (
    <div className="admin-status-row">
      <div>
        <div className="status-label">{label}</div>
        {sublabel ? <div className="status-sub">{sublabel}</div> : null}
      </div>
      <label className="gema-toggle" htmlFor={inputId}>
        <input
          id={inputId}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="gema-toggle-track" />
      </label>
    </div>
  );
}

export function RequiredMark() {
  return <span className="label-required"> *</span>;
}
