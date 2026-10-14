import type { Category } from "@/lib/catalog-types";

export type CategoryNode = Category & {
  children: CategoryNode[];
  depth: number;
};

export type FlatCategoryOption = {
  id: string;
  name: string;
  slug: string;
  depth: number;
  parent_id: string | null;
  is_active: boolean;
  label: string;
};

function sortByName(a: Category, b: Category) {
  return a.name.localeCompare(b.name, "es", { sensitivity: "base" });
}

/** Build a forest of category nodes with unlimited depth. */
export function buildCategoryForest(categories: Category[]): CategoryNode[] {
  const byParent = new Map<string | null, Category[]>();
  for (const category of categories) {
    const key = category.parent_id;
    const list = byParent.get(key) ?? [];
    list.push(category);
    byParent.set(key, list);
  }
  for (const list of byParent.values()) {
    list.sort(sortByName);
  }

  function build(parentId: string | null, depth: number): CategoryNode[] {
    const kids = byParent.get(parentId) ?? [];
    return kids.map((category) => ({
      ...category,
      depth,
      children: build(category.id, depth + 1),
    }));
  }

  return build(null, 0);
}

/** Depth-first flatten for selects and admin tables. */
export function flattenCategoryForest(
  nodes: CategoryNode[],
  options?: { indent?: string },
): FlatCategoryOption[] {
  const indent = options?.indent ?? "— ";
  const out: FlatCategoryOption[] = [];

  function walk(list: CategoryNode[]) {
    for (const node of list) {
      const prefix = indent.repeat(node.depth);
      out.push({
        id: node.id,
        name: node.name,
        slug: node.slug,
        depth: node.depth,
        parent_id: node.parent_id,
        is_active: node.is_active,
        label: `${prefix}${node.name}`,
      });
      if (node.children.length) walk(node.children);
    }
  }

  walk(nodes);
  return out;
}

export function flattenCategories(
  categories: Category[],
  options?: { indent?: string },
): FlatCategoryOption[] {
  return flattenCategoryForest(buildCategoryForest(categories), options);
}

/** Ancestor chain from root → parent of `category` (excludes self). */
export function getCategoryAncestors(
  category: Category,
  categories: Category[],
): Category[] {
  const byId = new Map(categories.map((c) => [c.id, c]));
  const path: Category[] = [];
  let current = category.parent_id ? byId.get(category.parent_id) : undefined;
  const seen = new Set<string>();
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    path.unshift(current);
    current = current.parent_id ? byId.get(current.parent_id) : undefined;
  }
  return path;
}

/** Direct children of a category (sorted). */
export function getDirectChildren(
  parentId: string,
  categories: Category[],
): Category[] {
  return categories.filter((c) => c.parent_id === parentId).sort(sortByName);
}

/** Nested subtree rooted at `categoryId`, or null if missing. */
export function getSubtreeNode(
  categoryId: string,
  categories: Category[],
): CategoryNode | null {
  const forest = buildCategoryForest(categories);

  function find(nodes: CategoryNode[]): CategoryNode | null {
    for (const node of nodes) {
      if (node.id === categoryId) return node;
      const nested = find(node.children);
      if (nested) return nested;
    }
    return null;
  }

  return find(forest);
}

/** Count nodes in a subtree (excluding the root node itself). */
export function countDescendants(node: CategoryNode): number {
  let total = 0;
  for (const child of node.children) {
    total += 1 + countDescendants(child);
  }
  return total;
}

/** Full path label: "Padre / Hija / Nieta". */
export function getCategoryPathLabel(
  category: Category,
  categories: Category[],
): string {
  const ancestors = getCategoryAncestors(category, categories);
  return [...ancestors.map((a) => a.name), category.name].join(" / ");
}

/** Exclude a category and all its descendants (for parent pickers). */
export function excludeCategorySubtree(
  options: FlatCategoryOption[],
  excludeId: string | null | undefined,
): FlatCategoryOption[] {
  if (!excludeId) return options;
  const editingIndex = options.findIndex((o) => o.id === excludeId);
  if (editingIndex < 0) {
    return options.filter((o) => o.id !== excludeId);
  }
  const editingDepth = options[editingIndex].depth;
  const blocked = new Set<string>([excludeId]);
  for (let i = editingIndex + 1; i < options.length; i++) {
    if (options[i].depth <= editingDepth) break;
    blocked.add(options[i].id);
  }
  return options.filter((o) => !blocked.has(o.id));
}

/** Filter options by name or full path (accent-insensitive). */
export function filterCategoryOptions(
  options: FlatCategoryOption[],
  query: string,
  categories: Category[],
): FlatCategoryOption[] {
  const q = query.trim().toLowerCase();
  if (!q) return options;
  const byId = new Map(categories.map((c) => [c.id, c]));
  return options.filter((option) => {
    if (option.name.toLowerCase().includes(q)) return true;
    if (option.slug.toLowerCase().includes(q)) return true;
    const cat = byId.get(option.id);
    if (!cat) return false;
    return getCategoryPathLabel(cat, categories).toLowerCase().includes(q);
  });
}
