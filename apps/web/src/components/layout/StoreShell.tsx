import { Suspense, type ReactNode } from "react";

import { StoreFooter } from "@/components/layout/StoreFooter";
import { StoreHeader } from "@/components/layout/StoreHeader";

function HeaderFallback() {
  return <div className="gema-header h-16" aria-hidden />;
}

export function StoreShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-transparent text-foreground">
      <Suspense fallback={<HeaderFallback />}>
        <StoreHeader />
      </Suspense>
      <div className="flex flex-1 flex-col">{children}</div>
      <StoreFooter />
    </div>
  );
}
