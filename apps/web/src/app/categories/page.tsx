import { StoreShell } from "@/components/layout/StoreShell";
import { CategoryDirectory } from "@/components/categories/CategoryDirectory";
import {
  buildCategoryForest,
  loadCategories,
} from "@/lib/catalog-loader";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Categorías | GEMA Technology",
  description:
    "Explora el catálogo de GEMA Technology por familias y subcategorías.",
};

export const dynamic = "force-dynamic";

export default async function CategoriesPage() {
  const result = await loadCategories();
  const categories = result.data ?? [];
  const forest = buildCategoryForest(categories);

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-10">
        <h1 className="font-display text-2xl font-semibold">Categorías</h1>
        <p className="mt-1 max-w-2xl text-sm text-secondary">
          Navega la jerarquía completa: cada familia puede tener hijos, nietos y
          niveles más profundos. Expande las ramas para encontrar el segmento
          exacto.
        </p>

        {result.error ? (
          <p className="gema-panel mt-8 px-4 py-3 text-sm text-secondary">
            {result.error.message}
          </p>
        ) : null}

        {!result.error ? <CategoryDirectory forest={forest} /> : null}
      </main>
    </StoreShell>
  );
}
