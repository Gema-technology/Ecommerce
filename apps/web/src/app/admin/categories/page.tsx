"use client";

import { AdminShell } from "@/components/admin/AdminShell";
import { CategoryManager } from "@/components/admin/CategoryManager";

export default function AdminCategoriesPage() {
  return (
    <AdminShell title="Categorías">
      <CategoryManager />
    </AdminShell>
  );
}
