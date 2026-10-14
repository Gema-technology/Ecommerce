"use client";

import Link from "next/link";
import { useMemo, useState, type CSSProperties } from "react";

import { cn } from "@/lib/cn";

export type CategoryCarouselItem = {
  id: string;
  name: string;
  slug: string;
  imageUrl: string | null;
  imageAlt: string | null;
};

function CategorySlide({
  item,
  duplicate,
}: {
  item: CategoryCarouselItem;
  duplicate?: boolean;
}) {
  return (
    <li
      className="w-[min(72vw,16.5rem)] shrink-0 sm:w-[15rem] lg:w-[16rem]"
      aria-hidden={duplicate || undefined}
    >
      <Link
        href={`/categories/${item.slug}`}
        tabIndex={duplicate ? -1 : undefined}
        className="gema-card gema-card-interactive group/card flex h-full flex-col overflow-hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="gema-card-header">
          <span className="gema-card-label">Categoría</span>
          <span
            className="gema-status-dot gema-status-dot--primary"
            aria-hidden
          />
        </div>
        <div className="gema-card-media relative aspect-[4/5] overflow-hidden">
          {item.imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={item.imageUrl}
              alt={duplicate ? "" : (item.imageAlt ?? item.name)}
              draggable={false}
              className="pointer-events-none h-full w-full object-contain p-6 transition duration-500 ease-[cubic-bezier(0.16,1,0.3,1)] group-hover/card:scale-[1.05]"
            />
          ) : (
            <div
              className="gema-card-media-placeholder flex h-full w-full items-center justify-center"
              aria-hidden
            >
              <span className="font-mono text-2xl font-medium tracking-tight text-navy/20 transition duration-150 group-hover/card:text-primary/40">
                {item.name.slice(0, 2).toUpperCase()}
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3">
          <h3 className="min-w-0 truncate font-display text-base font-semibold tracking-tight text-navy transition duration-150 group-hover/card:text-primary">
            {item.name}
          </h3>
          <span
            className="shrink-0 font-mono text-xs text-muted transition duration-150 group-hover/card:text-primary"
            aria-hidden
          >
            →
          </span>
        </div>
      </Link>
    </li>
  );
}

export function CategoryCarousel({
  items,
}: {
  items: CategoryCarouselItem[];
}) {
  const [paused, setPaused] = useState(false);

  // Enough copies so the track always fills wide screens and loops seamlessly.
  const loopItems = useMemo(() => {
    if (!items.length) return [];
    const copies = items.length < 4 ? 4 : 2;
    return Array.from({ length: copies }, (_, copy) =>
      items.map((item) => ({ item, copy })),
    ).flat();
  }, [items]);

  const durationSec = Math.max(28, items.length * 7);

  if (!items.length) {
    return <p className="text-sm text-muted">No hay categorías activas.</p>;
  }

  return (
    <div
      className="gema-marquee relative"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
          setPaused(false);
        }
      }}
    >
      <div className="gema-marquee-fade gema-marquee-fade-left" aria-hidden />
      <div className="gema-marquee-fade gema-marquee-fade-right" aria-hidden />

      <div className="overflow-hidden">
        <ul
          className={cn(
            "gema-marquee-track flex w-max gap-5",
            paused && "is-paused",
          )}
          style={{ "--marquee-duration": `${durationSec}s` } as CSSProperties}
          aria-label="Carrusel de categorías"
        >
          {loopItems.map(({ item, copy }) => (
            <CategorySlide
              key={`${item.id}-${copy}`}
              item={item}
              duplicate={copy > 0}
            />
          ))}
        </ul>
      </div>
    </div>
  );
}
