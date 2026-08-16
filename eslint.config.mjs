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
  // Minimal targeted rule overrides for Bklit UI registry-generated chart components
  {
    files: [
      "src/components/charts/bar-chart.tsx",
      "src/components/charts/bar-x-axis.tsx",
      "src/components/charts/bar-y-axis.tsx",
      "src/components/charts/loading-sweep.tsx",
      "src/components/charts/use-animated-y-domains.ts",
      "src/components/charts/use-chart-phase-orchestrator.ts",
      "src/components/charts/use-enter-complete.ts",
      "src/components/charts/use-mount-progress.ts",
      "src/components/charts/tooltip/date-ticker.tsx",
      "src/components/charts/tooltip/tooltip-box.tsx",
      "src/components/charts/tooltip/chart-tooltip.tsx",
      "src/components/editor/PaletteStudio.tsx",
    ],
    rules: {
      // Generated Bklit UI chart animation & tooltip hooks access refs and sync phase states during VisX scale calculations
      "react-hooks/refs": "off",
      "react-hooks/set-state-in-effect": "off",
      "@typescript-eslint/no-explicit-any": "off",
    },
  },
]);

export default eslintConfig;
