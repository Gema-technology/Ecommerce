"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";

export function HomeCtaBand() {
  return (
    <section aria-labelledby="home-cta" className="gema-cta-band">
      <div className="gema-container">
        <Reveal variant="blur">
          <div className="gema-cta-band-inner">
            <div>
              <p className="gema-card-label gema-cta-band-label">Listo para elegir</p>
              <h2 id="home-cta" className="gema-cta-band-title">
                Encuentra el equipo que tu trabajo necesita.
              </h2>
              <p className="gema-cta-band-desc">
                Revisa el catálogo completo o empieza por categoría. Stock
                actualizado y compra en minutos.
              </p>
            </div>
            <div className="gema-cta-band-actions">
              <Link href="/products" className="btn-primary btn-lg group">
                Ver catálogo
                <ArrowRight
                  className="h-4 w-4 transition duration-150 group-hover:translate-x-0.5"
                  aria-hidden
                />
              </Link>
              <Link href="/categories" className="btn-ghost btn-lg gema-cta-band-ghost">
                Ir a categorías
              </Link>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
