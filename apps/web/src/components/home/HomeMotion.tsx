"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactNode } from "react";

import { Reveal } from "@/components/motion/Reveal";

export function HomeHeroCopy() {
  return (
    <div>
      <Reveal variant="blur" delay={40}>
        <p className="gema-card-label mb-3">GEMA Technology</p>
        <h1 className="gema-hero-title">
          Tecnología que <span className="accent">vende resultados.</span>
        </h1>
      </Reveal>
      <Reveal delay={140}>
        <p className="gema-hero-lead">
          Laptops y equipos seleccionados para profesionales en Ecuador. Stock
          real, precios claros y envío a todo el país.
        </p>
      </Reveal>
      <Reveal delay={240}>
        <div className="gema-hero-actions">
          <Link href="/products" className="btn-primary btn-lg group">
            Ver catálogo
            <ArrowRight
              className="h-4 w-4 transition duration-150 group-hover:translate-x-0.5"
              aria-hidden
            />
          </Link>
          <Link href="/categories" className="btn-ghost btn-lg">
            Explorar categorías
          </Link>
        </div>
      </Reveal>
    </div>
  );
}

export function HomeHeroVisual({ children }: { children: ReactNode }) {
  return (
    <Reveal variant="scale" delay={180} className="gema-hero-visual">
      {children}
    </Reveal>
  );
}

export function SectionIntro({
  titleId,
  title,
  description,
  action,
}: {
  titleId: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="gema-section-header">
      <Reveal>
        <div>
          <h2 id={titleId} className="gema-section-title">
            {title}
          </h2>
          <p className="gema-section-desc">{description}</p>
        </div>
      </Reveal>
      {action ? <Reveal delay={100}>{action}</Reveal> : null}
    </div>
  );
}
