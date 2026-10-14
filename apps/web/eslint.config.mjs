import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Justified (Fase 0C): rule flags legitimate client data-fetch on mount,
      // form reset from props, and hydration sync. Migrating those to a shared
      // data layer / Suspense would be an architecture change, not a quality fix.
      // Keep other react-hooks rules enabled.
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
