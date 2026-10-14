import Link from "next/link";

import type { Category } from "@/lib/catalog-api";

export function CategoryCard({ category }: { category: Category }) {
  return (
    <Link
      href={`/categories/${category.slug}`}
      className="gema-card gema-card-interactive group/card block overflow-hidden focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
    >
      <div className="gema-card-header">
        <span className="gema-card-label">Categoría</span>
        <span
          className="gema-status-dot gema-status-dot--primary"
          aria-hidden
        />
      </div>
      {category.image_url ? (
        <div className="gema-card-media aspect-[16/10] overflow-hidden border-b border-border bg-surface-secondary">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={category.image_url}
            alt=""
            className="h-full w-full object-contain p-4 transition duration-300 group-hover/card:scale-[1.03]"
          />
        </div>
      ) : null}
      <div className="gema-card-body">
        <h2 className="font-display line-clamp-2 text-lg font-semibold tracking-tight text-navy transition duration-150 group-hover/card:text-primary">
          {category.name}
        </h2>
        {category.description ? (
          <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-secondary">
            {category.description}
          </p>
        ) : (
          <p className="mt-2 font-mono text-xs text-muted">VER →</p>
        )}
      </div>
    </Link>
  );
}
