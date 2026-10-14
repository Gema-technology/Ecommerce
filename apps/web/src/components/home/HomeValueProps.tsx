"use client";

import { ClipboardList, Headphones, ScanSearch } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";
import { SectionIntro } from "@/components/home/HomeMotion";

const VALUE_ITEMS = [
  {
    icon: ScanSearch,
    title: "Catálogo curado",
    description:
      "Seleccionamos laptops y periféricos por rendimiento real, no por moda. Menos ruido, mejores opciones.",
  },
  {
    icon: ClipboardList,
    title: "Compra clara",
    description:
      "Precio visible, disponibilidad al momento y checkout directo. Sabes qué compras antes de pagar.",
  },
  {
    icon: Headphones,
    title: "Acompañamiento",
    description:
      "Te ayudamos a elegir el equipo correcto y a dar seguimiento a tu pedido hasta la entrega.",
  },
] as const;

export function HomeValueProps() {
  return (
    <section aria-labelledby="home-why" className="gema-section-muted">
      <div className="gema-container">
        <SectionIntro
          titleId="home-why"
          title="Por qué comprar en GEMA"
          description="No somos un marketplace genérico. Somos una tienda especializada en tecnología para trabajo serio."
        />
        <ul className="gema-value-grid">
          {VALUE_ITEMS.map((item, index) => (
            <li key={item.title}>
              <Reveal delay={index * 80}>
                <article className="gema-value-item">
                  <span className="gema-value-index" aria-hidden>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <item.icon className="gema-value-icon" aria-hidden />
                  <h3 className="gema-value-title">{item.title}</h3>
                  <p className="gema-value-desc">{item.description}</p>
                </article>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
