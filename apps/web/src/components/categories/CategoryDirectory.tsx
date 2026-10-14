import Link from "next/link";

import { CategoryTreeList } from "@/components/categories/CategoryTreeList";
import type { CategoryNode } from "@/lib/category-tree";
import { countDescendants } from "@/lib/category-tree";

export function CategoryDirectory({ forest }: { forest: CategoryNode[] }) {
  if (!forest.length) {
    return (
      <p className="mt-8 text-sm text-secondary">No hay categorías activas.</p>
    );
  }

  return (
    <div className="mt-8 grid gap-5 lg:grid-cols-2">
      {forest.map((root) => {
        const nested = countDescendants(root);
        return (
          <section
            key={root.id}
            className="gema-panel-elevated flex min-h-[12rem] flex-col overflow-hidden"
          >
            <header className="border-b border-border px-5 py-4">
              <div className="flex items-start gap-4">
                {root.image_url ? (
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-[var(--radius-sm)] border border-border bg-surface-secondary">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={root.image_url}
                      alt=""
                      className="max-h-full max-w-full object-contain p-1.5"
                    />
                  </div>
                ) : null}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-mono text-[10px] tracking-wider text-muted">
                        FAMILIA
                      </p>
                      <h2 className="mt-1 font-display text-lg font-semibold tracking-tight text-navy">
                        <Link
                          href={`/categories/${root.slug}`}
                          className="transition hover:text-primary"
                        >
                          {root.name}
                        </Link>
                      </h2>
                      {root.description ? (
                        <p className="mt-1.5 line-clamp-2 text-sm text-secondary">
                          {root.description}
                        </p>
                      ) : null}
                    </div>
                    <div className="shrink-0 text-right">
                      <p className="font-mono text-[10px] text-muted">NIVELES</p>
                      <p className="mt-0.5 font-mono text-sm tabular-nums text-secondary">
                        {nested}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </header>
            <div className="flex-1 px-3 py-3">
              {root.children.length ? (
                <CategoryTreeList
                  nodes={root.children}
                  defaultOpenDepth={2}
                />
              ) : (
                <p className="px-2 py-2 text-sm text-muted">
                  Sin subcategorías —{" "}
                  <Link
                    href={`/categories/${root.slug}`}
                    className="text-secondary underline-offset-2 hover:text-primary hover:underline"
                  >
                    ver productos
                  </Link>
                </p>
              )}
            </div>
            <footer className="border-t border-border px-5 py-3">
              <Link
                href={`/categories/${root.slug}`}
                className="font-mono text-xs text-primary transition hover:underline"
              >
                Ver todo en {root.name} →
              </Link>
            </footer>
          </section>
        );
      })}
    </div>
  );
}
