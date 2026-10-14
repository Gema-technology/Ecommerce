"use client";

import Link from "next/link";

import { Reveal } from "@/components/motion/Reveal";
import { SectionIntro } from "@/components/home/HomeMotion";

export type HomeBrandItem = {
  id: string;
  name: string;
  slug: string;
  logoUrl: string | null;
};

export function HomeBrandBand({ brands }: { brands: HomeBrandItem[] }) {
  if (brands.length === 0) return null;

  return (
    <section aria-labelledby="home-brands" className="gema-section-alt">
      <div className="gema-container">
        <SectionIntro
          titleId="home-brands"
          title="Marcas que trabajamos"
          description="Fabricantes con respaldo y presencia en nuestro catálogo."
          action={
            <Link href="/brands" className="btn-ghost shrink-0 self-start sm:self-auto">
              Ver todas →
            </Link>
          }
        />
        <ul className="gema-brand-band">
          {brands.map((brand, index) => (
            <li key={brand.id}>
              <Reveal delay={index * 40}>
                <Link
                  href={`/products?brand=${brand.slug}`}
                  className="gema-brand-band-item"
                >
                  {brand.logoUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={brand.logoUrl} alt="" />
                  ) : (
                    <span className="font-mono text-sm font-semibold tracking-wide text-navy/40">
                      {brand.name.slice(0, 3).toUpperCase()}
                    </span>
                  )}
                  <span className="gema-brand-band-name">{brand.name}</span>
                </Link>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
