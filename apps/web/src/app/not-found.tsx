import { NotFoundView } from "@/components/shared/NotFoundView";

export default function NotFound() {
  return (
    <NotFoundView
      title="¡Ups! Página no encontrada"
      description="La página que buscas puede haber sido eliminada, cambió de nombre o no está disponible temporalmente."
      primaryHref="/"
      primaryLabel="Ir al inicio"
      secondaryHref="/products"
      secondaryLabel="Ver productos"
    />
  );
}
