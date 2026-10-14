import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

type Tone = "cyan" | "violet" | "success" | "warning" | "error" | "muted";

const TONE: Record<Tone, string> = {
  cyan: "gema-badge-cyan",
  violet: "gema-badge-violet",
  success: "gema-badge-success",
  warning: "gema-badge-warning",
  error: "gema-badge-error",
  muted: "gema-badge-muted",
};

export function Badge({
  tone = "muted",
  className,
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: Tone;
  children?: ReactNode;
}) {
  return (
    <span className={cn("gema-badge", TONE[tone], className)} {...props}>
      {children}
    </span>
  );
}
