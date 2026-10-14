"use client";

import { Menu, Search, ShoppingCart } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

import { BrandMark } from "@/components/brand/BrandMark";
import { useAuth } from "@/components/auth/AuthProvider";
import { CartDrawer } from "@/components/cart/CartDrawer";
import { useCart } from "@/components/cart/CartProvider";
import { AccountMenu } from "@/components/layout/AccountMenu";
import { AccountNavItems } from "@/components/layout/AccountNavItems";
import { SearchOverlay } from "@/components/layout/SearchOverlay";
import { ThemeToggle } from "@/components/theme/ThemeToggle";
import { Drawer } from "@/components/ui/drawer";
import { cn } from "@/lib/cn";

const NAV = [
  { href: "/products", label: "Productos" },
  { href: "/categories", label: "Categorías" },
  { href: "/brands", label: "Marcas" },
  { href: "/products?sort=newest", label: "Ofertas" },
] as const;

export function StoreHeader() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading, logout, isAdmin } = useAuth();
  const { itemCount } = useCart();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const closeMobile = useCallback(() => setMobileOpen(false), []);
  const closeSearch = useCallback(() => setSearchOpen(false), []);
  const closeCart = useCallback(() => setCartOpen(false), []);

  const openMobile = useCallback(() => {
    setSearchOpen(false);
    setCartOpen(false);
    setMobileOpen(true);
  }, []);

  const openSearch = useCallback(() => {
    setMobileOpen(false);
    setCartOpen(false);
    window.setTimeout(() => setSearchOpen(true), 0);
  }, []);

  const openCart = useCallback(() => {
    setMobileOpen(false);
    setSearchOpen(false);
    window.setTimeout(() => setCartOpen(true), 0);
  }, []);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        openSearch();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openSearch]);

  async function onLogout() {
    setMobileOpen(false);
    await logout();
  }

  function navActive(label: string) {
    const sort = searchParams.get("sort");
    if (label === "Ofertas") {
      return pathname.startsWith("/products") && sort === "newest";
    }
    if (label === "Productos") {
      return pathname.startsWith("/products") && sort !== "newest";
    }
    if (label === "Categorías") {
      return pathname.startsWith("/categories");
    }
    if (label === "Marcas") {
      return pathname.startsWith("/brands");
    }
    return false;
  }

  const cartAria =
    itemCount > 0 ? `Abrir carrito (${itemCount})` : "Abrir carrito";

  return (
    <>
      <header
        className={cn(
          "gema-header sticky top-0 z-50",
          scrolled && "is-scrolled",
        )}
      >
        <div className="gema-container relative z-10 flex items-center gap-1 sm:gap-2 lg:gap-8">
          <button
            type="button"
            className="btn-ghost btn-icon relative z-20 shrink-0 lg:hidden"
            aria-label="Abrir menú"
            aria-expanded={mobileOpen}
            onClick={openMobile}
          >
            <Menu className="h-5 w-5" aria-hidden />
          </button>

          <div className="min-w-0 flex-1 overflow-hidden lg:flex-none lg:shrink-0">
            <BrandMark />
          </div>

          <nav
            className="hidden min-w-0 flex-1 items-center justify-center gap-0.5 lg:flex"
            aria-label="Principal"
          >
            {NAV.map((item) => {
              const active = navActive(item.label);
              return (
                <Link
                  key={item.label}
                  href={item.href}
                  className={cn("gema-nav-link", active && "is-active")}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="relative z-20 ml-auto flex shrink-0 items-center justify-end gap-0.5 lg:gap-1">
            <ThemeToggle />

            <button
              type="button"
              className="btn-ghost btn-icon"
              aria-label="Buscar productos"
              onClick={openSearch}
            >
              <Search className="h-5 w-5" aria-hidden />
            </button>

            <button
              type="button"
              className="btn-ghost btn-icon relative"
              aria-label={cartAria}
              onClick={openCart}
            >
              <ShoppingCart className="h-5 w-5" aria-hidden />
              {itemCount > 0 ? (
                <span
                  key={itemCount}
                  className="gema-cart-badge animate-cart-pulse absolute right-0.5 top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold"
                  aria-hidden
                >
                  {itemCount > 99 ? "99+" : itemCount}
                </span>
              ) : null}
            </button>

            <AccountMenu />
          </div>
        </div>
      </header>

      <SearchOverlay open={searchOpen} onClose={closeSearch} />
      <CartDrawer open={cartOpen} onClose={closeCart} />

      <Drawer
        open={mobileOpen}
        title="GEMA Technology"
        onClose={closeMobile}
        side="left"
        fullScreenOnMobile
      >
        <nav
          className="flex flex-col gap-0.5 pb-[max(1rem,env(safe-area-inset-bottom))]"
          aria-label="Móvil"
        >
          <Link
            href="/"
            className={cn(
              "px-3 py-3.5 text-base text-secondary",
              pathname === "/" && "bg-surface-hover font-medium text-foreground",
            )}
            onClick={closeMobile}
          >
            Inicio
          </Link>
          {NAV.map((item) => {
            const active = navActive(item.label);
            return (
              <Link
                key={item.label}
                href={item.href}
                className={cn(
                  "px-3 py-3.5 text-base text-secondary",
                  active && "bg-surface-hover font-medium text-primary",
                )}
                aria-current={active ? "page" : undefined}
                onClick={closeMobile}
              >
                {item.label}
              </Link>
            );
          })}

          <div className="my-3 border-t border-border" />

          <button
            type="button"
            className="flex items-center gap-2 px-3 py-3.5 text-left text-base text-secondary"
            onClick={() => {
              closeMobile();
              openSearch();
            }}
          >
            <Search className="h-4 w-4 shrink-0" aria-hidden />
            Buscar
          </button>

          <div className="my-3 border-t border-border" />

          {!loading ? (
            <AccountNavItems
              user={user}
              isAdmin={isAdmin}
              variant="mobile"
              onNavigate={closeMobile}
              onLogout={() => void onLogout()}
            />
          ) : null}
        </nav>
      </Drawer>
    </>
  );
}
