import Link from "next/link";

import { cn } from "@/lib/cn";

type Props = {
  compact?: boolean;
  /** Stack “Technology” under GEMA — fits narrow sidebars. */
  stacked?: boolean;
  className?: string;
  href?: string | null;
};

export function BrandMark({
  compact = false,
  stacked = false,
  className,
  href = "/",
}: Props) {
  const label = "GEMA Technology";

  const content = (
    <span className={cn("inline-flex min-w-0 items-baseline", className)}>
      <span
        className={cn(
          "font-display font-bold tracking-[-0.03em] text-foreground",
          stacked
            ? "flex min-w-0 flex-col leading-[1.05]"
            : "inline",
          compact ? "text-lg sm:text-xl" : "text-xl sm:text-[1.35rem]",
        )}
        aria-hidden
      >
        <span>
          GE<span className="text-primary">MA</span>
          {!stacked ? (
            <span className="ml-1.5 font-semibold tracking-[-0.02em]">
              Technology
            </span>
          ) : null}
        </span>
        {stacked ? (
          <span className="text-[0.78em] font-semibold tracking-[-0.02em]">
            Technology
          </span>
        ) : null}
      </span>
      <span className="sr-only">{label}</span>
    </span>
  );

  if (href == null) return content;
  return (
    <Link
      href={href}
      aria-label={label}
      className="inline-flex min-w-0 max-w-full items-center focus-visible:outline-none"
    >
      {content}
    </Link>
  );
}
