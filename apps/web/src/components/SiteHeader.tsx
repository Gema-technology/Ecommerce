import Link from "next/link";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand/BrandMark";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

export function SiteHeader({ children }: { children?: ReactNode }) {
  return (
    <header className="gema-header">
      <div className="gema-container flex h-16 items-center justify-between gap-3">
        <BrandMark />
        <nav className="flex items-center gap-2 text-sm text-secondary">
          <ThemeToggle />
          {children ?? (
            <Link href="/login" className="btn-ghost">
              Iniciar sesión
            </Link>
          )}
        </nav>
      </div>
    </header>
  );
}
