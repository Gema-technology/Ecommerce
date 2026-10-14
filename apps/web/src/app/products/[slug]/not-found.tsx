import { NotFoundView } from "@/components/shared/NotFoundView";

export default function ProductNotFound() {
  return (
    <NotFoundView
      title="Producto no encontrado"
      description="El producto que buscas no existe o ya no está disponible."
      primaryHref="/products"
      primaryLabel="Ver productos"
      secondaryHref="/"
      secondaryLabel="Ir al inicio"
    />
  );
}
