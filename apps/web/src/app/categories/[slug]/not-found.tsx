import { NotFoundView } from "@/components/shared/NotFoundView";

export default function CategoryNotFound() {
  return (
    <NotFoundView
      title="Categoría no encontrada"
      description="La categoría no existe o no está activa."
      primaryHref="/categories"
      primaryLabel="Ver categorías"
      secondaryHref="/products"
      secondaryLabel="Ver productos"
    />
  );
}
