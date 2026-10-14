"use client";

import type { CSSProperties, ReactNode } from "react";

import { cn } from "@/lib/cn";
import { useInView } from "@/lib/use-in-view";

type RevealProps = {
  children: ReactNode;
  className?: string;
  /** Stagger delay in ms */
  delay?: number;
  variant?: "up" | "fade" | "scale" | "blur";
  once?: boolean;
};

export function Reveal({
  children,
  className,
  delay = 0,
  variant = "up",
  once = true,
}: RevealProps) {
  const { ref, inView } = useInView({ once });

  return (
    <div
      ref={ref}
      className={cn(
        "gema-reveal",
        `gema-reveal-${variant}`,
        inView && "is-visible",
        className,
      )}
      style={{ "--reveal-delay": `${delay}ms` } as CSSProperties}
    >
      {children}
    </div>
  );
}
