import Link from "next/link";

import { BrandMark } from "@/components/brand/BrandMark";

export function StoreFooter() {
  return (
    <footer className="gema-footer mt-auto">
      <div className="gema-container grid gap-10 py-14 sm:grid-cols-2 lg:grid-cols-4">
        <div className="sm:col-span-2 lg:col-span-1">
          <BrandMark href="/" />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-secondary">
            Tecnología premium para profesionales. Catálogo curado, stock real y
            experiencia de compra de alto nivel.
          </p>
        </div>
        <div>
          <p className="gema-card-label">Explorar</p>
          <ul className="mt-4 space-y-2.5 text-sm text-secondary">
            <li>
              <Link href="/products">Productos</Link>
            </li>
            <li>
              <Link href="/categories">Categorías</Link>
            </li>
            <li>
              <Link href="/brands">Marcas</Link>
            </li>
            <li>
              <Link href="/products?sort=newest">Ofertas</Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="gema-card-label">Cuenta</p>
          <ul className="mt-4 space-y-2.5 text-sm text-secondary">
            <li>
              <Link href="/cart">Carrito</Link>
            </li>
            <li>
              <Link href="/orders">Órdenes</Link>
            </li>
            <li>
              <Link href="/login">Iniciar sesión</Link>
            </li>
            <li>
              <Link href="/register">Registrarse</Link>
            </li>
          </ul>
        </div>
        <div>
          <p className="gema-card-label">Soporte</p>
          <ul className="mt-4 space-y-2.5 text-sm text-secondary">
            <li>
              <Link href="/account">Mi cuenta</Link>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border">
        <div className="gema-container flex flex-col gap-2 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between">
          <p className="font-mono text-xs text-muted">
            © {new Date().getFullYear()} GEMA Technology
          </p>
          <p className="font-mono text-xs text-muted">EC · TECH</p>
        </div>
      </div>
    </footer>
  );
}
