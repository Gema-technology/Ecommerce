import { StoreShell } from "@/components/layout/StoreShell";
import { CatalogPageSkeleton } from "@/components/shared/LoadingState";

export default function ProductsLoading() {
  return (
    <StoreShell>
      <CatalogPageSkeleton />
    </StoreShell>
  );
}
