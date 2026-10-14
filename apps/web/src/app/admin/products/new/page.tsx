"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import { AppLoading } from "@/components/shared/AppLoading";

/** Create lives in a modal on the products list. */
export default function NewProductPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/admin/products");
  }, [router]);

  return (
    <AdminShell title="Nuevo producto">
      <AppLoading compact label="Redirigiendo" hideHint className="!py-12" />
    </AdminShell>
  );
}
