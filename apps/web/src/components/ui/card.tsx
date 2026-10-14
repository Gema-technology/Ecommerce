import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";

export function Card({
  className,
  interactive,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  interactive?: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      className={cn(
        "gema-card",
        interactive && "gema-card-interactive",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function Panel({
  className,
  elevated,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & {
  elevated?: boolean;
  children?: ReactNode;
}) {
  return (
    <div
      className={cn(elevated ? "gema-panel-elevated" : "gema-panel", className)}
      {...props}
    >
      {children}
    </div>
  );
}
