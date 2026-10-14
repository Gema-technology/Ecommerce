import { ApiError } from "@/lib/auth-api";
import {
  catalogApi,
  type Brand,
  type Category,
  type Product,
  type ProductListResponse,
  type ProductQuery,
} from "@/lib/catalog-api";

export type CatalogLoadError = {
  kind: "api" | "not_found" | "unknown";
  message: string;
};

export async function loadCategories(): Promise<
  { data: Category[]; error: null } | { data: null; error: CatalogLoadError }
> {
  try {
    return { data: await catalogApi.listCategories(), error: null };
  } catch (err) {
    return { data: null, error: toError(err) };
  }
}

export async function loadBrands(options?: {
  category?: string;
}): Promise<
  { data: Brand[]; error: null } | { data: null; error: CatalogLoadError }
> {
  try {
    return {
      data: await catalogApi.listBrands(false, {
        category: options?.category,
      }),
      error: null,
    };
  } catch (err) {
    return { data: null, error: toError(err) };
  }
}

export async function loadProducts(
  query: ProductQuery = {},
): Promise<
  | { data: ProductListResponse; error: null }
  | { data: null; error: CatalogLoadError }
> {
  try {
    return { data: await catalogApi.listProducts(query), error: null };
  } catch (err) {
    return { data: null, error: toError(err) };
  }
}

export async function loadProduct(
  slug: string,
): Promise<
  { data: Product; error: null } | { data: null; error: CatalogLoadError }
> {
  try {
    return { data: await catalogApi.getProduct(slug), error: null };
  } catch (err) {
    return { data: null, error: toError(err) };
  }
}

export async function loadCategory(
  slug: string,
): Promise<
  { data: Category; error: null } | { data: null; error: CatalogLoadError }
> {
  try {
    return { data: await catalogApi.getCategory(slug), error: null };
  } catch (err) {
    return { data: null, error: toError(err) };
  }
}

function toError(err: unknown): CatalogLoadError {
  if (err instanceof ApiError) {
    if (err.status === 404) {
      return { kind: "not_found", message: err.message };
    }
    if (err.status === 503) {
      return {
        kind: "api",
        message: "No pudimos conectar con el catálogo. Intenta de nuevo más tarde.",
      };
    }
    return { kind: "api", message: err.message };
  }
  return {
    kind: "unknown",
    message: "Ocurrió un error inesperado. Intenta de nuevo más tarde.",
  };
}

export {
  buildCategoryForest,
  flattenCategories,
  getCategoryAncestors,
  getCategoryPathLabel,
  getDirectChildren,
  getSubtreeNode,
  countDescendants,
  excludeCategorySubtree,
  filterCategoryOptions,
} from "@/lib/category-tree";
export type { CategoryNode, FlatCategoryOption } from "@/lib/category-tree";

/** @deprecated Prefer buildCategoryForest / flattenCategories for deep trees. */
export function buildCategoryTree(categories: Category[]) {
  const roots = categories.filter((c) => !c.parent_id);
  const childrenOf = (parentId: string) =>
    categories.filter((c) => c.parent_id === parentId);
  return { roots, childrenOf };
}
