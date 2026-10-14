import { StoreShell } from "@/components/layout/StoreShell";
import { CatalogPageSkeleton } from "@/components/shared/LoadingState";

export default function CategorySlugLoading() {
  return (
    <StoreShell>
      <CatalogPageSkeleton />
    </StoreShell>
  );
}
