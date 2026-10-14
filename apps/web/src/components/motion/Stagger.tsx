"use client";

import type { ReactNode } from "react";

import { cn } from "@/lib/cn";
import { useInView } from "@/lib/use-in-view";

/** Marks a container so children with CSS nth-child delays stagger in. */
export function Stagger({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const { ref, inView } = useInView({ rootMargin: "0px 0px -6% 0px" });

  return (
    <div
      ref={ref}
      className={cn("gema-stagger", inView && "is-visible", className)}
    >
      {children}
    </div>
  );
}
