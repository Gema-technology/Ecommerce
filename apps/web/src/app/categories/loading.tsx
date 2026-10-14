import { StoreShell } from "@/components/layout/StoreShell";
import { CategoryGridSkeleton } from "@/components/shared/LoadingState";
import { Skeleton } from "@/components/ui/skeleton";

export default function CategoriesLoading() {
  return (
    <StoreShell>
      <main className="gema-container flex-1 py-12 sm:py-16">
        <Skeleton className="h-12 w-56" />
        <Skeleton className="mt-3 h-5 w-72 max-w-full" />
        <div className="mt-12">
          <CategoryGridSkeleton />
        </div>
      </main>
    </StoreShell>
  );
}
