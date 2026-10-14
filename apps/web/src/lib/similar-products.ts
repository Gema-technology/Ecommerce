import type { Product } from "@/lib/catalog-types";

/** Spec keys that matter most for “similar laptop” matching. */
const SIMILARITY_SPEC_KEYS = [
  "processor",
  "cpu",
  "ram",
  "memory",
  "storage",
  "disk",
  "gpu",
  "graphics",
  "screen_size",
  "display",
  "resolution",
] as const;

function normalizeSpecValue(value: unknown): string {
  return String(value ?? "")
    .toLowerCase()
    .replace(/,/g, ".")
    .replace(/\s+/g, " ")
    .replace(/\b(gb|tb|mhz|ghz|inch|pulgadas|"|”)\b/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function specTokens(value: unknown): Set<string> {
  const normalized = normalizeSpecValue(value);
  if (!normalized) return new Set();
  return new Set(
    normalized
      .split(/[\s/|+\-]+/)
      .map((t) => t.trim())
      .filter((t) => t.length >= 2),
  );
}

function specOverlapScore(a: unknown, b: unknown): number {
  const left = normalizeSpecValue(a);
  const right = normalizeSpecValue(b);
  if (!left || !right) return 0;
  if (left === right) return 8;
  if (left.includes(right) || right.includes(left)) return 5;

  const ta = specTokens(a);
  const tb = specTokens(b);
  if (!ta.size || !tb.size) return 0;
  let shared = 0;
  for (const token of ta) {
    if (tb.has(token)) shared += 1;
  }
  if (shared === 0) return 0;
  const ratio = shared / Math.max(ta.size, tb.size);
  if (ratio >= 0.5) return 4;
  if (shared >= 2) return 2;
  return 1;
}

function priceProximityScore(base: Product, candidate: Product): number {
  const a = Number(base.price?.amount);
  const b = Number(candidate.price?.amount);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) return 0;
  const ratio = Math.abs(a - b) / a;
  if (ratio <= 0.15) return 4;
  if (ratio <= 0.35) return 2;
  if (ratio <= 0.6) return 1;
  return 0;
}

export function similarityScore(base: Product, candidate: Product): number {
  if (base.id === candidate.id) return -1;

  let score = 0;
  if (candidate.category.id === base.category.id) score += 12;
  else if (candidate.category.slug === base.category.slug) score += 10;

  if (candidate.brand.id === base.brand.id) score += 6;

  const baseSpecs = base.specifications ?? {};
  const candSpecs = candidate.specifications ?? {};
  for (const key of SIMILARITY_SPEC_KEYS) {
    if (key in baseSpecs && key in candSpecs) {
      score += specOverlapScore(baseSpecs[key], candSpecs[key]);
    }
  }

  // Soft bonus for any other shared exact spec values.
  for (const [key, value] of Object.entries(baseSpecs)) {
    if ((SIMILARITY_SPEC_KEYS as readonly string[]).includes(key)) continue;
    if (!(key in candSpecs)) continue;
    if (normalizeSpecValue(value) && normalizeSpecValue(value) === normalizeSpecValue(candSpecs[key])) {
      score += 2;
    }
  }

  score += priceProximityScore(base, candidate);
  return score;
}

/**
 * Rank candidates by shared specs / brand / category / price.
 * Keeps products with score > 0, highest first.
 */
export function pickSimilarProducts(
  base: Product,
  candidates: Product[],
  limit = 8,
): Product[] {
  const ranked = candidates
    .map((item) => ({ item, score: similarityScore(base, item) }))
    .filter((row) => row.score > 0)
    .sort((a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name));

  const seen = new Set<string>();
  const out: Product[] = [];
  for (const row of ranked) {
    if (seen.has(row.item.id)) continue;
    seen.add(row.item.id);
    out.push(row.item);
    if (out.length >= limit) break;
  }
  return out;
}

/** Short human hint about why items are related. */
export function similarProductsDescription(base: Product): string {
  const parts: string[] = [];
  const specs = base.specifications ?? {};
  const ram = specs.ram ?? specs.memory;
  const cpu = specs.processor ?? specs.cpu;
  const storage = specs.storage ?? specs.disk;
  if (cpu) parts.push(String(cpu));
  if (ram) parts.push(`${String(ram)} RAM`);
  if (storage) parts.push(String(storage));

  if (parts.length) {
    return `Opciones parecidas por categoría, marca y características (${parts.slice(0, 3).join(" · ")}).`;
  }
  return `Otras opciones en ${base.category.name}${base.brand.name ? ` y marca ${base.brand.name}` : ""}.`;
}
