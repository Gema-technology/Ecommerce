import { ProductCard } from "@/components/products/ProductCard";
import { Stagger } from "@/components/motion/Stagger";
import type { Product } from "@/lib/catalog-api";

export function ProductGrid({ products }: { products: Product[] }) {
  return (
    <Stagger className="grid gap-6 sm:grid-cols-2 sm:gap-7 lg:grid-cols-3 lg:gap-8">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </Stagger>
  );
}
