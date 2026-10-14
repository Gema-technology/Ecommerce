import { describe, expect, it } from "vitest";

import type { Product } from "@/lib/catalog-types";
import {
  pickSimilarProducts,
  similarityScore,
} from "@/lib/similar-products";

function product(partial: Partial<Product> & Pick<Product, "id" | "name">): Product {
  return {
    id: partial.id,
    sku: partial.sku ?? partial.id,
    name: partial.name,
    slug: partial.slug ?? partial.id,
    short_description: null,
    description: null,
    model: null,
    brand: partial.brand ?? { id: "b1", name: "ASUS", slug: "asus" },
    category: partial.category ?? {
      id: "c1",
      name: "Laptops",
      slug: "laptops",
    },
    specifications: partial.specifications ?? {},
    weight: null,
    warranty_months: null,
    is_active: true,
    images: [],
    price: partial.price ?? { amount: "1000", currency: "USD", price_type: "RETAIL" },
    availability: "IN_STOCK",
  };
}

describe("similar products", () => {
  const base = product({
    id: "base",
    name: "Base",
    specifications: {
      processor: "Intel Core i7-13700H",
      ram: "16GB",
      storage: "512GB SSD",
      gpu: "RTX 4060",
    },
    price: { amount: "1200", currency: "USD", price_type: "RETAIL" },
  });

  it("ranks closer specs higher than unrelated", () => {
    const close = product({
      id: "close",
      name: "Close",
      specifications: {
        processor: "Intel Core i7-13700H",
        ram: "16 GB",
        storage: "512GB SSD",
        gpu: "RTX 4050",
      },
      price: { amount: "1150", currency: "USD", price_type: "RETAIL" },
    });
    const far = product({
      id: "far",
      name: "Far",
      brand: { id: "b2", name: "Dell", slug: "dell" },
      specifications: { processor: "Celeron N4020", ram: "4GB", storage: "128GB eMMC" },
      price: { amount: "350", currency: "USD", price_type: "RETAIL" },
    });

    expect(similarityScore(base, close)).toBeGreaterThan(similarityScore(base, far));
    expect(pickSimilarProducts(base, [far, close], 2).map((p) => p.id)).toEqual([
      "close",
      "far",
    ]);
  });

  it("excludes the base product itself", () => {
    const other = product({
      id: "other",
      name: "Other",
      specifications: { ram: "16GB" },
    });
    expect(pickSimilarProducts(base, [base, other], 5).map((p) => p.id)).toEqual([
      "other",
    ]);
  });
});
