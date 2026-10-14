"use client";

import { User } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth/AuthProvider";
import { AccountNavItems } from "@/components/layout/AccountNavItems";
import { InlineLoading } from "@/components/shared/AppLoading";

export function AccountMenu() {
  const { user, loading, logout, isAdmin } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointer = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onPointer);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  async function onLogout() {
    setOpen(false);
    await logout();
    router.push("/");
  }

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="btn-ghost btn-icon relative z-10 touch-manipulation"
        aria-label="Abrir cuenta"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <User className="pointer-events-none h-5 w-5" aria-hidden />
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          className="gema-popover account-menu-panel absolute right-0 z-[60] mt-2 origin-top-right animate-scale-in"
        >
          {loading ? (
            <div className="px-3 py-3">
              <InlineLoading label="Cargando…" />
            </div>
          ) : (
            <AccountNavItems
              user={user}
              isAdmin={isAdmin}
              onNavigate={() => setOpen(false)}
              onLogout={() => void onLogout()}
            />
          )}
        </div>
      ) : null}
    </div>
  );
}
