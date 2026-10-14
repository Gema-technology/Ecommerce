import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Truck } from "lucide-react";

import { StoreShell } from "@/components/layout/StoreShell";
import { AddToCartButton } from "@/components/cart/AddToCartButton";
import { ProductGallery } from "@/components/products/ProductGallery";
import { ProductGrid } from "@/components/products/ProductGrid";
import { ProductSpecifications } from "@/components/products/ProductSpecifications";
import { Badge } from "@/components/ui/badge";
import {
  availabilityLabel,
  formatPrice,
  formatSavings,
  getCompareAtPrice,
  shippingLabel,
} from "@/lib/catalog-api";
import { loadProduct, loadProducts } from "@/lib/catalog-loader";
import {
  pickSimilarProducts,
  similarProductsDescription,
} from "@/lib/similar-products";

export const dynamic = "force-dynamic";

type Params = Promise<{ slug: string }>;

function stockTone(availability: string): "success" | "warning" | "error" | "muted" {
  switch (availability) {
    case "IN_STOCK":
      return "success";
    case "LOW_STOCK":
      return "warning";
    case "OUT_OF_STOCK":
      return "error";
    default:
      return "muted";
  }
}

export async function generateMetadata({
  params,
}: {
  params: Params;
}): Promise<Metadata> {
  const { slug } = await params;
  const result = await loadProduct(slug);
  if (!result.data) {
    return {
      title: "Producto no encontrado | GEMA Technology",
    };
  }
  const product = result.data;
  const title = `${product.brand.name} ${product.name} | GEMA Technology`;
  const description =
    product.short_description ||
    product.description ||
    `${product.name} en GEMA Technology`;
  const image = product.images.find((i) => i.is_primary) ?? product.images[0];

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      type: "website",
      images: image ? [{ url: image.url, alt: image.alt_text ?? product.name }] : undefined,
    },
  };
}

export default async function ProductDetailPage({
  params,
}: {
  params: Params;
}) {
  const { slug } = await params;
  const result = await loadProduct(slug);

  if (result.error?.kind === "not_found") {
    notFound();
  }

  if (result.error || !result.data) {
    return (
      <StoreShell>
        <main className="gema-container flex-1 py-16">
          <h1 className="font-display text-2xl font-semibold">
            No pudimos cargar el producto
          </h1>
          <p className="mt-2 text-sm text-secondary">
            {result.error?.message ?? "Intenta de nuevo más tarde."}
          </p>
          <Link href="/products" className="btn-primary mt-6 inline-flex">
            Volver al catálogo
          </Link>
        </main>
      </StoreShell>
    );
  }

  const product = result.data;
  const priceText = formatPrice(product.price);
  const compareAt = getCompareAtPrice(product.price);
  const savings = formatSavings(product.price);
  const stock = availabilityLabel(product.availability);
  const shipping = shippingLabel(product.availability);

  const [byCategory, byBrand] = await Promise.all([
    loadProducts({
      category: product.category.slug,
      page: 1,
      page_size: 24,
      sort: "newest",
    }),
    loadProducts({
      brand: product.brand.slug,
      page: 1,
      page_size: 24,
      sort: "newest",
    }),
  ]);
  const relatedPool = [
    ...(byCategory.data?.items ?? []),
    ...(byBrand.data?.items ?? []),
  ];
  const related = pickSimilarProducts(product, relatedPool, 8);

  return (
    <StoreShell>
      <main className="gema-container flex-1 py-10 sm:py-14">
        <nav
          className="mb-8 flex min-w-0 items-center gap-2 text-sm text-secondary"
          aria-label="Miga de pan"
        >
          <Link
            href="/products"
            className="shrink-0 transition hover:text-foreground"
          >
            Productos
          </Link>
          <span className="shrink-0 text-muted">/</span>
          <Link
            href={`/categories/${product.category.slug}`}
            className="min-w-0 truncate transition hover:text-foreground"
          >
            {product.category.name}
          </Link>
          <span className="shrink-0 text-muted">/</span>
          <span className="min-w-0 truncate text-foreground">{product.name}</span>
        </nav>

        <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] lg:gap-16">
          <ProductGallery images={product.images} productName={product.name} />

          <div className="lg:pt-2">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              {product.brand.name}
            </p>
            <h1 className="font-display mt-3 text-3xl font-semibold tracking-tight text-navy sm:text-4xl lg:text-[2.75rem] lg:leading-[1.1]">
              {product.name}
            </h1>
            <p className="mt-3 text-sm text-secondary">
              SKU {product.sku}
              {product.model ? ` · Modelo ${product.model}` : ""}
            </p>

            <div className="mt-8 flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <p className="gema-price text-4xl">
                {priceText ?? "Consultar precio"}
              </p>
              {compareAt ? (
                <span className="gema-price-compare text-base">{compareAt}</span>
              ) : null}
            </div>
            {savings ? <p className="gema-price-save mt-2">{savings}</p> : null}
            {product.price?.price_type === "PROMOTIONAL" && !savings ? (
              <p className="mt-2 text-sm text-secondary">Precio promocional</p>
            ) : null}

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Badge tone={stockTone(product.availability ?? "")}>{stock}</Badge>
              {shipping ? (
                <span className="inline-flex items-center gap-1.5 text-sm text-secondary">
                  <Truck className="h-4 w-4" aria-hidden />
                  {shipping}
                </span>
              ) : null}
            </div>

            {product.short_description ? (
              <p className="mt-8 text-base leading-relaxed text-secondary">
                {product.short_description}
              </p>
            ) : null}

            <div className="mt-8">
              <AddToCartButton productId={product.id} />
            </div>

            <p className="mt-8 text-sm text-secondary">
              Categoría:{" "}
              <Link
                href={`/categories/${product.category.slug}`}
                className="font-medium text-primary underline-offset-2 hover:underline"
              >
                {product.category.name}
              </Link>
            </p>
          </div>
        </div>

        {product.description ? (
          <section className="mt-16 sm:mt-20" aria-labelledby="product-description">
            <h2
              id="product-description"
              className="font-display text-2xl font-semibold tracking-tight text-navy"
            >
              Descripción
            </h2>
            <p className="mt-4 max-w-3xl whitespace-pre-wrap text-base leading-relaxed text-secondary">
              {product.description}
            </p>
          </section>
        ) : null}

        <section className="mt-16 sm:mt-20" aria-labelledby="product-specs">
          <h2
            id="product-specs"
            className="font-display text-2xl font-semibold tracking-tight text-navy"
          >
            Especificaciones
          </h2>
          <div className="mt-6 max-w-3xl">
            <ProductSpecifications specifications={product.specifications} />
          </div>
        </section>

        {related.length > 0 ? (
          <section className="mt-16 sm:mt-20" aria-labelledby="product-related">
            <div className="gema-section-header">
              <div>
                <h2
                  id="product-related"
                  className="gema-section-title"
                >
                  Productos similares
                </h2>
                <p className="gema-section-desc">
                  {similarProductsDescription(product)}
                </p>
              </div>
              <Link
                href={`/categories/${product.category.slug}`}
                className="btn-ghost shrink-0"
              >
                Ver categoría →
              </Link>
            </div>
            <ProductGrid products={related} />
          </section>
        ) : null}
      </main>
    </StoreShell>
  );
}
