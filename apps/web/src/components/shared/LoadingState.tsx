import { Skeleton } from "@/components/ui/skeleton";

export function ProductCardSkeleton() {
  return (
    <div className="gema-card overflow-hidden">
      <Skeleton className="aspect-square !rounded-none" />
      <div className="space-y-3 p-5">
        <Skeleton className="h-3 w-1/4" />
        <Skeleton className="h-5 w-4/5" />
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-3 w-2/5" />
        <Skeleton className="mt-2 h-11 w-full" />
      </div>
    </div>
  );
}

export function ProductGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-6 sm:grid-cols-2 sm:gap-7 lg:grid-cols-3 lg:gap-8">
      {Array.from({ length: count }).map((_, i) => (
        <ProductCardSkeleton key={i} />
      ))}
    </div>
  );
}

export function ProductDetailSkeleton() {
  return (
    <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
      <Skeleton className="aspect-square !rounded-[var(--radius-2xl)]" />
      <div className="space-y-4 lg:pt-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-10 w-4/5" />
        <Skeleton className="h-4 w-2/5" />
        <Skeleton className="mt-4 h-9 w-1/3" />
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-6 h-20 w-full" />
        <Skeleton className="mt-4 h-14 w-full" />
      </div>
    </div>
  );
}

export function CatalogPageSkeleton() {
  return (
    <div className="gema-container flex-1 py-12 sm:py-16">
      <Skeleton className="h-12 w-56" />
      <Skeleton className="mt-3 h-5 w-80 max-w-full" />
      <div className="mt-12 grid gap-8 lg:grid-cols-[17.5rem_1fr] lg:gap-12">
        <Skeleton className="hidden h-80 lg:block !rounded-[var(--radius-xl)]" />
        <div>
          <div className="mb-8 flex justify-between">
            <Skeleton className="h-5 w-28" />
            <Skeleton className="h-10 w-40" />
          </div>
          <ProductGridSkeleton count={6} />
        </div>
      </div>
    </div>
  );
}

export function HomePageSkeleton() {
  return (
    <>
      <div className="gema-container gema-hero-inner">
        <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
          <div className="space-y-5">
            <Skeleton className="h-14 w-4/5 max-w-md" />
            <Skeleton className="h-14 w-3/5 max-w-sm" />
            <Skeleton className="h-5 w-full max-w-md" />
            <Skeleton className="h-12 w-44" />
            <div className="flex gap-6 pt-4">
              <Skeleton className="h-3 w-12" />
              <Skeleton className="h-3 w-12" />
              <Skeleton className="h-3 w-12" />
              <Skeleton className="h-3 w-12" />
            </div>
          </div>
          <Skeleton className="mx-auto aspect-square w-full max-w-md !rounded-[var(--radius-2xl)]" />
        </div>
      </div>
      <div className="gema-container py-16">
        <Skeleton className="mb-8 h-9 w-48" />
        <div className="flex gap-5 overflow-hidden">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton
              key={i}
              className="aspect-[4/5] w-[15rem] shrink-0 !rounded-[var(--radius-2xl)]"
            />
          ))}
        </div>
      </div>
      <div className="gema-container pb-20">
        <Skeleton className="mb-8 h-9 w-40" />
        <ProductGridSkeleton count={3} />
      </div>
    </>
  );
}

export function CategoryGridSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-28 !rounded-[var(--radius-2xl)]" />
      ))}
    </div>
  );
}
