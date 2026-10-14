import Link from "next/link";
import {
  Boxes,
  Briefcase,
  ClipboardList,
  CreditCard,
  FileText,
  Package,
  Receipt,
  Settings,
  ShoppingCart,
  Tags,
  Truck,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

const CARDS: {
  href: string;
  label: string;
  desc: string;
  icon: LucideIcon;
}[] = [
  { href: "/admin/categories", label: "Categorías", desc: "Jerarquía del catálogo", icon: Tags },
  { href: "/admin/brands", label: "Marcas", desc: "Fabricantes y marcas", icon: Boxes },
  { href: "/admin/products", label: "Productos", desc: "SKU, fichas e imágenes", icon: Package },
  { href: "/admin/catalogo", label: "Catálogo cotiz.", desc: "Costos y márgenes", icon: FileText },
  {
    href: "/admin/cotizaciones",
    label: "Cotizaciones",
    desc: "Proformas e historial",
    icon: ClipboardList,
  },
  {
    href: "/admin/suppliers",
    label: "Proveedores",
    desc: "Costos y disponibilidad",
    icon: Truck,
  },
  {
    href: "/admin/inventory",
    label: "Inventario",
    desc: "Stock, reservas y movimientos",
    icon: Warehouse,
  },
  { href: "/admin/orders", label: "Pedidos", desc: "Compras y envíos", icon: ShoppingCart },
  {
    href: "/admin/comprobantes",
    label: "Comprobantes",
    desc: "Notas de venta y facturas SRI",
    icon: Receipt,
  },
  { href: "/admin/payments", label: "Pagos", desc: "Intentos e historial", icon: CreditCard },
  {
    href: "/admin/customers",
    label: "Clientes",
    desc: "Compradores y contra entrega",
    icon: Users,
  },
  {
    href: "/admin/employees",
    label: "Equipo",
    desc: "Empleados e invitaciones",
    icon: Briefcase,
  },
  {
    href: "/admin/configuracion",
    label: "Configuración",
    desc: "Negocio, banco y envío",
    icon: Settings,
  },
  {
    href: "/admin/sri",
    label: "Facturación SRI",
    desc: "RIMPE, certificado y secuenciales",
    icon: FileText,
  },
];

export function QuickLinks() {
  return (
    <section>
      <h2 className="font-display mb-3 text-lg font-semibold">Accesos rápidos</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.href}
              href={card.href}
              className="gema-panel group flex gap-3 p-4 transition hover:border-cyan"
            >
              <span
                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-border bg-surface-secondary text-primary transition group-hover:border-primary/30 group-hover:bg-primary group-hover:text-white"
                aria-hidden
              >
                <Icon className="h-4 w-4" strokeWidth={2} />
              </span>
              <span className="min-w-0">
                <span className="font-display block font-semibold text-foreground">
                  {card.label}
                </span>
                <span className="text-sm text-secondary">{card.desc}</span>
              </span>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
