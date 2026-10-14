"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";

/** Legacy path — redirects to Clientes. */
export default function AdminUsersRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/admin/customers");
  }, [router]);

  return (
    <AdminShell title="Usuarios">
      <p className="text-sm text-secondary">Redirigiendo a Clientes…</p>
    </AdminShell>
  );
}
