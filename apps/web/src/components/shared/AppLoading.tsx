import { BrandMark } from "@/components/brand/BrandMark";
import { StoreShell } from "@/components/layout/StoreShell";
import { cn } from "@/lib/cn";

type AppLoadingProps = {
  label?: string;
  /** Full page chrome (header + footer) */
  withShell?: boolean;
  /** Smaller padding for drawers / embedded panels */
  compact?: boolean;
  /** Hide secondary “Preparando…” line */
  hideHint?: boolean;
  className?: string;
};

/** Premium brand loader — routes, auth gates, and page-level waits. */
export function AppLoading({
  label = "Cargando",
  withShell = false,
  compact = false,
  hideHint = false,
  className,
}: AppLoadingProps) {
  const content = (
    <div
      className={cn(
        "flex flex-1 flex-col items-center justify-center px-6",
        compact ? "py-10" : "py-20",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div
        className={cn(
          "relative flex flex-col items-center",
          compact ? "gap-5" : "gap-8",
        )}
      >
        <div className="relative">
          <span className="gema-loader-ring" aria-hidden />
          <span className="gema-loader-ring gema-loader-ring-delay" aria-hidden />
          <div
            className={cn(
              "relative z-10 flex items-center justify-center border border-border bg-surface",
              compact ? "h-12 w-12" : "h-16 w-16",
            )}
          >
            <span
              className={cn(
                "font-display font-bold tracking-tight text-navy",
                compact ? "text-sm" : "text-lg",
              )}
            >
              GE<span className="text-primary">MA</span>
              <span className="ml-1.5 font-semibold">Technology</span>
            </span>
          </div>
        </div>

        <div className="text-center">
          <p
            className={cn(
              "font-display font-semibold tracking-tight text-navy",
              compact ? "text-sm" : "text-base",
            )}
          >
            {label}
          </p>
          {!hideHint && !compact ? (
            <p className="mt-1.5 text-sm text-muted">Preparando tu experiencia</p>
          ) : null}
        </div>

        <div className="flex items-center gap-1.5" aria-hidden>
          <span className="gema-loader-dot" />
          <span className="gema-loader-dot gema-loader-dot-2" />
          <span className="gema-loader-dot gema-loader-dot-3" />
        </div>
      </div>
    </div>
  );

  if (withShell) {
    return <StoreShell>{content}</StoreShell>;
  }

  return content;
}

/** Compact inline spinner for lists, menus, chat */
export function InlineLoading({
  label = "Cargando…",
  className,
  labelHidden = false,
}: {
  label?: string;
  className?: string;
  labelHidden?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 text-sm text-secondary",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label={label}
    >
      <span className="gema-spinner shrink-0" aria-hidden />
      {!labelHidden ? <span>{label}</span> : null}
    </span>
  );
}

/** Full-bleed overlay while a client action runs */
export function LoadingOverlay({
  label = "Cargando",
  show = true,
}: {
  label?: string;
  show?: boolean;
}) {
  if (!show) return null;
  return (
    <div
      className="gema-backdrop-animate fixed inset-0 z-[90] flex items-center justify-center bg-[color-mix(in_srgb,var(--gema-bg)_72%,transparent)] backdrop-blur-[6px]"
      role="status"
      aria-live="assertive"
      aria-busy="true"
    >
      <div className="gema-panel-elevated flex flex-col items-center gap-5 px-10 py-8">
        <BrandMark href={null} compact />
        <span className="gema-spinner gema-spinner-lg" aria-hidden />
        <p className="text-sm font-medium text-secondary">{label}</p>
      </div>
    </div>
  );
}
