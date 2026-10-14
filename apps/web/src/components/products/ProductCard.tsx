import Link from "next/link";
import { ArrowUpRight, Package, Truck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import {
  availabilityLabel,
  formatPrice,
  formatSavings,
  getCompareAtPrice,
  shippingLabel,
  type Product,
} from "@/lib/catalog-api";
import { cn } from "@/lib/cn";

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

function statusDotClass(availability: string): string {
  switch (availability) {
    case "IN_STOCK":
      return "gema-status-dot--primary";
    case "LOW_STOCK":
      return "gema-status-dot--warning";
    case "OUT_OF_STOCK":
      return "gema-status-dot--error";
    default:
      return "gema-status-dot--muted";
  }
}

export function ProductCard({ product }: { product: Product }) {
  const image =
    product.images.find((i) => i.is_primary) ??
    product.images.slice().sort((a, b) => a.sort_order - b.sort_order)[0];
  const priceText = formatPrice(product.price);
  const compareAt = getCompareAtPrice(product.price);
  const savings = formatSavings(product.price);
  const stock = availabilityLabel(product.availability);
  const shipping = shippingLabel(product.availability);
  const availability = product.availability ?? "";

  return (
    <article
      className={cn(
        "gema-card gema-card-interactive group/card flex flex-col overflow-hidden",
      )}
    >
      <div className="gema-card-header">
        <span className="gema-card-label">{product.brand.name}</span>
        <span
          className={cn("gema-status-dot", statusDotClass(availability))}
          title={stock}
          aria-label={stock}
        />
      </div>

      <Link
        href={`/products/${product.slug}`}
        className="flex flex-1 flex-col focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
      >
        <div className="gema-card-media relative overflow-hidden">
          {image ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={image.url}
              alt={image.alt_text ?? product.name}
              className="aspect-square w-full object-contain p-6 transition duration-150 sm:p-8"
            />
          ) : (
            <div className="gema-card-media-placeholder flex aspect-square flex-col items-center justify-center gap-2">
              <Package className="gema-card-icon h-10 w-10" aria-hidden />
              <span className="text-sm text-muted">Sin imagen</span>
            </div>
          )}
        </div>

        <div className="gema-card-body">
          <h2 className="font-display line-clamp-2 text-base font-semibold leading-snug tracking-tight text-navy transition duration-150 group-hover/card:text-primary">
            {product.name}
          </h2>

          <div className="gema-card-specs">
            {product.category?.name ? (
              <span className="gema-spec-chip">{product.category.name}</span>
            ) : null}
            <Badge tone={stockTone(availability)}>{stock}</Badge>
            {savings ? (
              <span className="gema-spec-chip">{savings}</span>
            ) : null}
            {shipping ? (
              <span className="gema-spec-chip inline-flex items-center gap-1">
                <Truck className="h-3 w-3" aria-hidden />
                {shipping}
              </span>
            ) : null}
          </div>
        </div>
      </Link>

      <div className="gema-card-footer">
        <div>
          <p className="gema-price text-lg">
            {priceText ?? "Consultar precio"}
          </p>
          {compareAt ? (
            <span className="gema-price-compare">{compareAt}</span>
          ) : null}
        </div>
        <Link
          href={`/products/${product.slug}`}
          className="btn-primary btn-sm shrink-0"
        >
          Ver
          <ArrowUpRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </div>
    </article>
  );
}
