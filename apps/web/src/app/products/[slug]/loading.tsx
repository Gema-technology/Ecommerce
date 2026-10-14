import { StoreShell } from "@/components/layout/StoreShell";
import { ProductDetailSkeleton } from "@/components/shared/LoadingState";
import { Skeleton } from "@/components/ui/skeleton";

export default function ProductDetailLoading() {
  return (
    <StoreShell>
      <main className="gema-container flex-1 py-10 sm:py-14">
        <Skeleton className="mb-8 h-4 w-64 max-w-full" />
        <ProductDetailSkeleton />
      </main>
    </StoreShell>
  );
}
