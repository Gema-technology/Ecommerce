import { AppLoading } from "@/components/shared/AppLoading";

export default function AdminLoading() {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <AppLoading label="Cargando admin" />
    </div>
  );
}
