import Image from "next/image";
import Link from "next/link";

import { StoreShell } from "@/components/layout/StoreShell";
import { cn } from "@/lib/cn";

type NotFoundViewProps = {
  title: string;
  description: string;
  primaryHref?: string;
  primaryLabel?: string;
  secondaryHref?: string;
  secondaryLabel?: string;
  /** When false, render without StoreShell (global app not-found). */
  withShell?: boolean;
  className?: string;
};

export function NotFoundView({
  title,
  description,
  primaryHref = "/",
  primaryLabel = "Ir al inicio",
  secondaryHref = "/products",
  secondaryLabel = "Ver productos",
  withShell = true,
  className,
}: NotFoundViewProps) {
  const content = (
    <main
      className={cn(
        "gema-container flex flex-1 flex-col items-center justify-center py-12 sm:py-16",
        className,
      )}
    >
      <div className="grid w-full max-w-5xl items-center gap-10 md:grid-cols-2 md:gap-12">
        <div className="order-2 text-center md:order-1 md:text-left">
          <p className="gema-badge gema-badge-primary mb-4">Error 404</p>
          <h1 className="font-display text-3xl font-bold tracking-tight text-navy sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 max-w-md text-sm text-secondary sm:text-base md:mx-0 mx-auto">
            {description}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3 md:justify-start">
            <Link href={primaryHref} className="btn-primary">
              {primaryLabel}
            </Link>
            <Link href={secondaryHref} className="btn-outline">
              {secondaryLabel}
            </Link>
          </div>
        </div>
        <div className="order-1 flex justify-center md:order-2">
          <Image
            src="/illustrations/404.png"
            alt=""
            width={640}
            height={480}
            priority
            className="h-auto w-full max-w-md object-contain md:max-w-none"
          />
        </div>
      </div>
    </main>
  );

  if (!withShell) {
    return (
      <div className="gema-bg-base flex min-h-full flex-col text-foreground">
        {content}
      </div>
    );
  }

  return <StoreShell>{content}</StoreShell>;
}
