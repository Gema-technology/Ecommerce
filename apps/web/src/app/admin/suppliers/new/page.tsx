"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import { AppLoading } from "@/components/shared/AppLoading";

/** Create lives in a modal on the suppliers list. */
export default function NewSupplierPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/suppliers");
  }, [router]);

  return (
    <AdminShell title="Nuevo proveedor">
      <AppLoading compact label="Redirigiendo" hideHint className="!py-12" />
    </AdminShell>
  );
}
