"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  Boxes,
  Briefcase,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  CreditCard,
  FileText,
  LayoutDashboard,
  Menu,
  Package,
  Receipt,
  Settings,
  ShoppingCart,
  Store,
  Tags,
  Truck,
  Users,
  Warehouse,
  type LucideIcon,
} from "lucide-react";

import { BrandMark } from "@/components/brand/BrandMark";
import { RequireAuth } from "@/components/auth/RequireAuth";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Drawer } from "@/components/ui/drawer";
import { cn } from "@/lib/cn";

const COLLAPSE_KEY = "gema.admin.sidebar.collapsed";

type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

type NavGroup = {
  id: string;
  label: string;
  items: NavItem[];
};

const NAV_GROUPS: NavGroup[] = [
  {
    id: "principal",
    label: "Principal",
    items: [{ href: "/admin", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    id: "catalogo",
    label: "Catálogo",
    items: [
      { href: "/admin/products", label: "Productos", icon: Package },
      { href: "/admin/categories", label: "Categorías", icon: Tags },
      { href: "/admin/brands", label: "Marcas", icon: Boxes },
      { href: "/admin/catalogo", label: "Catálogo cotiz.", icon: FileText },
    ],
  },
  {
    id: "ventas",
    label: "Ventas",
    items: [
      { href: "/admin/orders", label: "Pedidos", icon: ShoppingCart },
      { href: "/admin/cotizaciones", label: "Cotizaciones", icon: ClipboardList },
      { href: "/admin/comprobantes", label: "Comprobantes", icon: Receipt },
      { href: "/admin/payments", label: "Pagos", icon: CreditCard },
    ],
  },
  {
    id: "personas",
    label: "Personas",
    items: [
      { href: "/admin/customers", label: "Clientes", icon: Users },
      { href: "/admin/employees", label: "Equipo", icon: Briefcase },
    ],
  },
  {
    id: "operaciones",
    label: "Operaciones",
    items: [
      { href: "/admin/inventory", label: "Inventario", icon: Warehouse },
      { href: "/admin/suppliers", label: "Proveedores", icon: Truck },
    ],
  },
  {
    id: "sistema",
    label: "Sistema",
    items: [
      { href: "/admin/configuracion", label: "Configuración", icon: Settings },
      { href: "/admin/sri", label: "Facturación SRI", icon: FileText },
    ],
  },
];

function isActive(pathname: string, href: string) {
  return href === "/admin" ? pathname === "/admin" : pathname.startsWith(href);
}

function AdminNavLinks({
  pathname,
  onNavigate,
  className = "admin-nav",
  collapsed = false,
}: {
  pathname: string;
  onNavigate?: () => void;
  className?: string;
  collapsed?: boolean;
}) {
  return (
    <nav className={className} aria-label="Administración">
      {NAV_GROUPS.map((group) => (
        <div key={group.id} className="admin-nav-group">
          <p className="admin-nav-label">{group.label}</p>
          {group.items.map((item) => {
            const Icon = item.icon;
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className="admin-nav-link"
                aria-current={active ? "page" : undefined}
                aria-label={collapsed ? item.label : undefined}
                title={collapsed ? item.label : undefined}
                onClick={onNavigate}
              >
                <span className="admin-nav-icon" aria-hidden>
                  <Icon absoluteStrokeWidth />
                </span>
                <span className="admin-nav-text">{item.label}</span>
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

function StoreLink({
  onNavigate,
  collapsed = false,
}: {
  onNavigate?: () => void;
  collapsed?: boolean;
}) {
  return (
    <Link
      href="/"
      className="admin-store-link"
      onClick={onNavigate}
      title={collapsed ? "Volver a la tienda" : undefined}
      aria-label={collapsed ? "Volver a la tienda" : undefined}
    >
      <span className="admin-store-link-icon" aria-hidden>
        <Store className="h-3.5 w-3.5" />
      </span>
      <span className="admin-store-link-text flex min-w-0 flex-1 flex-col leading-tight">
        <span>Volver a la tienda</span>
      </span>
      <ArrowLeft
        className="admin-store-link-arrow h-3.5 w-3.5 shrink-0 opacity-60"
        aria-hidden
      />
    </Link>
  );
}

export function AdminShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  function toggleCollapsed() {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  return (
    <RequireAuth roles={["ADMIN", "SUPER_ADMIN"]}>
      <div className="flex min-h-full bg-transparent text-foreground">
        <aside
          className={cn(
            "admin-aside",
            collapsed && "admin-aside--collapsed",
            ready && "admin-aside--ready",
          )}
          aria-label="Barra lateral de administración"
          data-collapsed={collapsed ? "true" : "false"}
        >
          <button
            type="button"
            className="admin-aside-toggle"
            onClick={toggleCollapsed}
            aria-label={collapsed ? "Expandir menú" : "Colapsar menú"}
            aria-expanded={!collapsed}
            title={collapsed ? "Expandir menú" : "Colapsar menú"}
          >
            {collapsed ? (
              <ChevronRight className="admin-aside-toggle-icon" aria-hidden />
            ) : (
              <ChevronLeft className="admin-aside-toggle-icon" aria-hidden />
            )}
          </button>

          <div className="admin-aside-inner">
            <div className="admin-aside-brand">
              <div className="admin-aside-brand-mark">
                <BrandMark href="/admin" stacked />
                <Link
                  href="/admin"
                  className="admin-aside-brand-mono"
                  aria-label="GEMA Technology — Gestión"
                >
                  GE<span className="text-primary">MA</span>
                </Link>
              </div>
              <div className="admin-aside-brand-meta">
                <span className="admin-aside-brand-dot" aria-hidden />
                <span className="admin-aside-brand-meta-text">Gestión</span>
              </div>
            </div>

            <AdminNavLinks pathname={pathname} collapsed={collapsed} />

            <div className="admin-aside-foot">
              <div className="admin-aside-foot-row">
                <span className="admin-aside-foot-hint">Apariencia</span>
                <ThemeToggle />
              </div>
              <StoreLink collapsed={collapsed} />
            </div>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="gema-header sticky top-0 z-40 lg:hidden">
            <div className="gema-container flex h-14 items-center gap-3">
              <button
                type="button"
                className="btn-ghost btn-icon touch-manipulation"
                aria-label="Abrir menú de administración"
                aria-expanded={mobileOpen}
                onClick={() => setMobileOpen(true)}
              >
                <Menu className="pointer-events-none h-5 w-5" aria-hidden />
              </button>
              <div className="min-w-0 flex-1">
                <BrandMark compact />
              </div>
              <ThemeToggle />
            </div>
          </header>

          <Drawer
            open={mobileOpen}
            title="Administración"
            onClose={() => setMobileOpen(false)}
            side="left"
            fullScreenOnMobile
          >
            <AdminNavLinks
              pathname={pathname}
              onNavigate={() => setMobileOpen(false)}
              className="admin-nav-mobile"
            />
            <div className="mt-4 border-t border-border pt-3">
              <StoreLink onNavigate={() => setMobileOpen(false)} />
            </div>
          </Drawer>

          <main className="gema-container min-w-0 flex-1 overflow-x-hidden py-6 sm:py-8 lg:py-10">
            <h1 className="font-display mb-6 text-xl font-bold tracking-tight text-foreground sm:mb-8 sm:text-2xl lg:text-3xl">
              {title}
            </h1>
            <div className="min-w-0">{children}</div>
          </main>
        </div>
      </div>
    </RequireAuth>
  );
}
