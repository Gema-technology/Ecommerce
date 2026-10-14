import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

type Variant =
  | "primary"
  | "secondary"
  | "ghost"
  | "outline"
  | "danger"
  | "success";

type Size = "sm" | "md" | "lg" | "icon" | "icon-sm";

const VARIANT_CLASS: Record<Variant, string> = {
  primary: "btn-primary",
  secondary: "btn-secondary",
  ghost: "btn-ghost",
  outline: "btn-outline",
  danger: "btn-danger",
  success: "btn-success",
};

const SIZE_CLASS: Record<Size, string> = {
  sm: "btn-sm",
  md: "btn-md",
  lg: "btn-lg",
  icon: "btn-icon",
  "icon-sm": "btn-icon btn-sm",
};

export function Button({
  variant = "primary",
  size = "md",
  className,
  children,
  loading,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children?: ReactNode;
}) {
  return (
    <button
      className={cn(VARIANT_CLASS[variant], SIZE_CLASS[size], className)}
      disabled={props.disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <span className="inline-flex items-center gap-2">
          <span
            className="gema-spinner !h-4 !w-4 border-[1.5px] border-current/25 !border-t-current"
            aria-hidden
          />
          <span>Cargando…</span>
        </span>
      ) : (
        children
      )}
    </button>
  );
}
