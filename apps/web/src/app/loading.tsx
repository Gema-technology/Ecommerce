import { AppLoading } from "@/components/shared/AppLoading";

/** Global route loading — shown while any page segment resolves. */
export default function Loading() {
  return <AppLoading withShell label="Cargando" />;
}
