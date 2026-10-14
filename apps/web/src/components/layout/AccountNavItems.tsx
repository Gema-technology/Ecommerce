"use client";

import Link from "next/link";
import {
  LayoutDashboard,
  LogIn,
  LogOut,
  Package,
  UserPlus,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import type { User } from "@/lib/auth-api";

type Props = {
  user: User | null;
  isAdmin: boolean;
  loading?: boolean;
  onNavigate?: () => void;
  onLogout?: () => void;
  variant?: "popover" | "mobile";
};

function initials(user: User) {
  const base = (user.first_name || user.email || "?").trim();
  const parts = base.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0]![0] ?? ""}${parts[1]![0] ?? ""}`.toUpperCase();
  }
  return base.slice(0, 2).toUpperCase();
}

function Item({
  href,
  icon: Icon,
  label,
  onClick,
  danger,
}: {
  href?: string;
  icon: LucideIcon;
  label: string;
  onClick?: () => void;
  danger?: boolean;
}) {
  const className = [
    "account-menu-item",
    danger ? "account-menu-item--danger" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const body = (
    <>
      <span className="account-menu-item-icon" aria-hidden>
        <Icon absoluteStrokeWidth />
      </span>
      {label}
    </>
  );

  if (href) {
    return (
      <Link role="menuitem" href={href} className={className} onClick={onClick}>
        {body}
      </Link>
    );
  }

  return (
    <button
      type="button"
      role="menuitem"
      className={className}
      onClick={onClick}
    >
      {body}
    </button>
  );
}

export function AccountNavItems({
  user,
  isAdmin,
  onNavigate,
  onLogout,
  variant = "popover",
}: Props) {
  const wrapClass =
    variant === "mobile" ? "account-menu-mobile" : "account-menu-list";

  if (user) {
    return (
      <div className={wrapClass}>
        <div className="account-menu-header">
          <span className="account-menu-avatar" aria-hidden>
            {initials(user)}
          </span>
          <div className="account-menu-meta">
            <p className="account-menu-name">
              {user.first_name || user.email}
            </p>
            <p className="account-menu-email">{user.email}</p>
          </div>
        </div>

        <Item
          href="/account"
          icon={UserRound}
          label="Mi cuenta"
          onClick={onNavigate}
        />
        <Item
          href="/orders"
          icon={Package}
          label="Mis pedidos"
          onClick={onNavigate}
        />
        {isAdmin ? (
          <Item
            href="/admin"
            icon={LayoutDashboard}
            label="Administración"
            onClick={onNavigate}
          />
        ) : null}

        <hr className="account-menu-divider" />

        <Item
          icon={LogOut}
          label="Cerrar sesión"
          danger
          onClick={onLogout}
        />
      </div>
    );
  }

  return (
    <div className={wrapClass}>
      <div className="account-menu-header">
        <span className="account-menu-avatar" aria-hidden>
          <UserRound />
        </span>
        <div className="account-menu-meta">
          <p className="account-menu-name">Bienvenido</p>
          <p className="account-menu-email">Accede a tu cuenta GEMA Technology</p>
        </div>
      </div>
      <Item href="/login" icon={LogIn} label="Iniciar sesión" onClick={onNavigate} />
      <Item
        href="/register"
        icon={UserPlus}
        label="Crear cuenta"
        onClick={onNavigate}
      />
    </div>
  );
}
