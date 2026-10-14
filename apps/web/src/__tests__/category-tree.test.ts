import { describe, expect, it } from "vitest";

import type { Category } from "@/lib/catalog-types";
import {
  buildCategoryForest,
  excludeCategorySubtree,
  filterCategoryOptions,
  flattenCategories,
  getCategoryAncestors,
  getCategoryPathLabel,
  getSubtreeNode,
} from "@/lib/category-tree";

function cat(
  id: string,
  name: string,
  parent_id: string | null = null,
): Category {
  return {
    id,
    name,
    slug: name.toLowerCase().replace(/\s+/g, "-"),
    description: null,
    image_url: null,
    parent_id,
    is_active: true,
  };
}

describe("category-tree", () => {
  const categories = [
    cat("1", "Impresión 3D"),
    cat("2", "Filamentos", "1"),
    cat("3", "PLA", "2"),
    cat("4", "PLA Premium", "3"),
    cat("5", "Laptops"),
    cat("6", "Gaming", "5"),
  ];

  it("builds unlimited-depth forest", () => {
    const forest = buildCategoryForest(categories);
    expect(forest).toHaveLength(2);
    expect(forest[0].name).toBe("Impresión 3D");
    expect(forest[0].children[0].name).toBe("Filamentos");
    expect(forest[0].children[0].children[0].name).toBe("PLA");
    expect(forest[0].children[0].children[0].children[0].name).toBe(
      "PLA Premium",
    );
    expect(forest[0].children[0].children[0].children[0].depth).toBe(3);
  });

  it("flattens with indentation labels", () => {
    const flat = flattenCategories(categories);
    expect(flat.map((o) => o.label)).toEqual([
      "Impresión 3D",
      "— Filamentos",
      "— — PLA",
      "— — — PLA Premium",
      "Laptops",
      "— Gaming",
    ]);
  });

  it("resolves ancestors and subtree", () => {
    const leaf = categories.find((c) => c.id === "4")!;
    const ancestors = getCategoryAncestors(leaf, categories);
    expect(ancestors.map((a) => a.name)).toEqual([
      "Impresión 3D",
      "Filamentos",
      "PLA",
    ]);
    expect(getCategoryPathLabel(leaf, categories)).toBe(
      "Impresión 3D / Filamentos / PLA / PLA Premium",
    );

    const subtree = getSubtreeNode("1", categories);
    expect(subtree?.children[0].children[0].children[0].name).toBe(
      "PLA Premium",
    );
  });

  it("excludes subtree and filters by path", () => {
    const flat = flattenCategories(categories);
    const withoutFilamentos = excludeCategorySubtree(flat, "2");
    expect(withoutFilamentos.map((o) => o.id)).toEqual(["1", "5", "6"]);

    const hits = filterCategoryOptions(flat, "pla premium", categories);
    expect(hits.map((o) => o.name)).toEqual(["PLA Premium"]);
  });
});
