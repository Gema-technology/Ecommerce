import Link from "next/link";

import {
  CategoryCarousel,
  type CategoryCarouselItem,
} from "@/components/categories/CategoryCarousel";
import { HomeBrandBand } from "@/components/home/HomeBrandBand";
import { HomeCtaBand } from "@/components/home/HomeCtaBand";
import {
  HomeHeroCopy,
  HomeHeroVisual,
  SectionIntro,
} from "@/components/home/HomeMotion";
import { HomeTrustStrip } from "@/components/home/HomeTrustStrip";
import { HomeValueProps } from "@/components/home/HomeValueProps";
import { StoreShell } from "@/components/layout/StoreShell";
import { ProductGrid } from "@/components/products/ProductGrid";
import {
  buildCategoryTree,
  loadBrands,
  loadCategories,
  loadProducts,
} from "@/lib/catalog-loader";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const [categoriesResult, productsResult, brandsResult] = await Promise.all([
    loadCategories(),
    loadProducts({ page: 1, page_size: 8, sort: "newest" }),
    loadBrands(),
  ]);

  const categories = categoriesResult.data ?? [];
  const { roots } = buildCategoryTree(categories);
  const featured = productsResult.data?.items ?? [];
  const brands = brandsResult.data ?? [];
  const apiError =
    categoriesResult.error || productsResult.error || brandsResult.error;

  const carouselCats = roots.slice(0, 10);
  const categoryImageResults = await Promise.all(
    carouselCats.map((cat) =>
      loadProducts({ category: cat.slug, page: 1, page_size: 1, sort: "newest" }),
    ),
  );

  const categoryCarouselItems: CategoryCarouselItem[] = carouselCats.map(
    (cat, index) => {
      if (cat.image_url) {
        return {
          id: cat.id,
          name: cat.name,
          slug: cat.slug,
          imageUrl: cat.image_url,
          imageAlt: cat.name,
        };
      }
      const product = categoryImageResults[index]?.data?.items[0];
      const image =
        product?.images.find((i) => i.is_primary) ??
        product?.images
          .slice()
          .sort((a, b) => a.sort_order - b.sort_order)[0];
      return {
        id: cat.id,
        name: cat.name,
        slug: cat.slug,
        imageUrl: image?.url ?? null,
        imageAlt: image?.alt_text ?? product?.name ?? null,
      };
    },
  );

  const heroProduct = featured[0];
  const heroImage =
    heroProduct?.images.find((i) => i.is_primary) ??
    heroProduct?.images.slice().sort((a, b) => a.sort_order - b.sort_order)[0];

  const brandBandItems = brands.slice(0, 8).map((b) => ({
    id: b.id,
    name: b.name,
    slug: b.slug,
    logoUrl: b.logo_url,
  }));

  return (
    <StoreShell>
      <section className="gema-hero">
        <div className="gema-container gema-hero-inner">
          <div className="grid items-center gap-12 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
            <HomeHeroCopy />

            <HomeHeroVisual>
              <div className="gema-hero-visual-frame">
                {heroImage ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={heroImage.url}
                    alt={
                      heroImage.alt_text ??
                      heroProduct?.name ??
                      "Producto destacado GEMA"
                    }
                  />
                ) : (
                  <div
                    className="gema-card-media-placeholder flex h-full w-full items-center justify-center p-10"
                    aria-hidden
                  >
                    <span className="font-mono text-4xl font-medium tracking-tight text-navy/15">
                      GEMA
                    </span>
                  </div>
                )}
              </div>
            </HomeHeroVisual>
          </div>
        </div>
      </section>

      <HomeTrustStrip />

      {apiError ? (
        <div className="gema-container pt-8">
          <p className="gema-panel border-warning/30 px-4 py-3 text-sm text-warning">
            {apiError.message}
          </p>
        </div>
      ) : null}

      <section aria-labelledby="home-categories" className="gema-section-alt">
        <div className="gema-container">
          <SectionIntro
            titleId="home-categories"
            title="Compra por categoría"
            description="Encuentra rápido el tipo de equipo que necesitas."
            action={
              <Link href="/categories" className="btn-ghost shrink-0 self-start sm:self-auto">
                Ver todas →
              </Link>
            }
          />
          <CategoryCarousel items={categoryCarouselItems} />
        </div>
      </section>

      <section aria-labelledby="home-featured" className="gema-section">
        <div className="gema-container">
          <SectionIntro
            titleId="home-featured"
            title="Recién llegados"
            description="Lo más nuevo del catálogo, listo para revisar y comprar."
            action={
              <Link href="/products" className="btn-ghost shrink-0 self-start sm:self-auto">
                Ver catálogo →
              </Link>
            }
          />
          {featured.length ? (
            <ProductGrid products={featured} />
          ) : (
            <p className="text-sm text-muted">Aún no hay productos publicados.</p>
          )}
        </div>
      </section>

      <HomeValueProps />

      <HomeBrandBand brands={brandBandItems} />

      <HomeCtaBand />
    </StoreShell>
  );
}
