"use client";

import { useMemo, useState } from "react";

import type { ProductImage } from "@/lib/catalog-api";
import { cn } from "@/lib/cn";

export function ProductGallery({
  images,
  productName,
}: {
  images: ProductImage[];
  productName: string;
}) {
  const sorted = useMemo(
    () =>
      images
        .slice()
        .sort((a, b) => {
          if (a.is_primary !== b.is_primary) return a.is_primary ? -1 : 1;
          return a.sort_order - b.sort_order;
        }),
    [images],
  );
  const [active, setActive] = useState(0);
  const current = sorted[active];

  if (!sorted.length) {
    return (
      <div className="gema-card-media-placeholder flex aspect-square items-center justify-center border border-border text-muted">
        Sin imágenes
      </div>
    );
  }

  return (
    <div>
      <div className="gema-card-media overflow-hidden border border-border">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          key={`${active}-${current.url}`}
          src={current.url}
          alt={current.alt_text ?? productName}
          className="animate-image-reveal aspect-square w-full object-contain p-8 sm:p-12"
        />
      </div>
      {sorted.length > 1 ? (
        <ul className="mt-4 grid grid-cols-4 gap-2 sm:grid-cols-5">
          {sorted.map((img, index) => (
            <li key={`${img.url}-${index}`}>
              <button
                type="button"
                className={cn(
                  "gema-card-media overflow-hidden border bg-surface-image p-0 transition duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
                  index === active
                    ? "border-primary"
                    : "border-border hover:border-primary/40",
                )}
                onClick={() => setActive(index)}
                aria-label={`Ver imagen ${index + 1}`}
                aria-pressed={index === active}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img.url}
                  alt={img.alt_text ?? `${productName} miniatura ${index + 1}`}
                  className="aspect-square w-full object-contain p-1.5"
                />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
