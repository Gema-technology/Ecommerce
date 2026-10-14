"use client";

import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { AppLoading } from "@/components/shared/AppLoading";

type RequireAuthProps = {
  children: ReactNode;
  roles?: string[];
  redirectTo?: string;
};

export function RequireAuth({
  children,
  roles,
  redirectTo = "/login",
}: RequireAuthProps) {
  const { user, loading, isAuthenticated } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!isAuthenticated) {
      router.replace(redirectTo);
      return;
    }
    if (roles && roles.length > 0) {
      const allowed = roles.some((role) => user?.roles.includes(role));
      if (!allowed) {
        router.replace("/account?error=forbidden");
      }
    }
  }, [loading, isAuthenticated, roles, user, router, redirectTo]);

  if (loading) {
    return <AppLoading label="Cargando sesión" hideHint />;
  }

  if (!isAuthenticated) {
    return null;
  }

  if (roles && roles.length > 0) {
    const allowed = roles.some((role) => user?.roles.includes(role));
    if (!allowed) {
      return (
        <div className="flex flex-1 items-center justify-center bg-surface p-8 font-medium text-error">
          Acceso denegado
        </div>
      );
    }
  }

  return <>{children}</>;
}
