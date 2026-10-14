"use client";

import { CreditCard, PackageCheck, ShieldCheck, Truck } from "lucide-react";

import { Reveal } from "@/components/motion/Reveal";

const TRUST_ITEMS = [
  {
    icon: Truck,
    title: "Envío a todo Ecuador",
    description: "Despacho a provincias con seguimiento del pedido.",
  },
  {
    icon: PackageCheck,
    title: "Stock real",
    description: "Lo que ves en catálogo está disponible para comprar.",
  },
  {
    icon: ShieldCheck,
    title: "Garantía de fábrica",
    description: "Equipos con respaldo del fabricante y soporte GEMA.",
  },
  {
    icon: CreditCard,
    title: "Pago seguro",
    description: "Tarjeta con PayPhone o transferencia bancaria.",
  },
] as const;

export function HomeTrustStrip() {
  return (
    <section aria-label="Beneficios de comprar en GEMA" className="gema-trust-strip">
      <div className="gema-container">
        <ul className="gema-trust-grid">
          {TRUST_ITEMS.map((item, index) => (
            <li key={item.title}>
              <Reveal delay={index * 60}>
                <div className="gema-trust-item">
                  <item.icon className="gema-trust-icon" aria-hidden />
                  <div>
                    <p className="gema-trust-title">{item.title}</p>
                    <p className="gema-trust-desc">{item.description}</p>
                  </div>
                </div>
              </Reveal>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
