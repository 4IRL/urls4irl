import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

import destructuredParams from "./eslint-rules/destructured-params.js";
import destructuredParamsBaseline from "./eslint-rules/destructured-params-baseline.json" with { type: "json" };

export default [
  {
    files: ["**/*.ts"],
    languageOptions: { parser: tsParser },
    plugins: { "@typescript-eslint": tsPlugin },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      // The recommended config does not ignore underscore-prefixed identifiers by default.
      // This codebase uses `_foo` to mark intentionally-unused destructured elements,
      // function args, and `catch (_err)` bindings — this override aligns the rule with that convention.
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          destructuredArrayIgnorePattern: "^_",
        },
      ],
      "no-console": "error",
      // Single-letter names: `$` (jQuery) and `_` (unused) are the only exceptions.
      "id-length": [
        "error",
        { min: 2, exceptions: ["$", "_"], properties: "never" },
      ],
      // id-length skips type parameters, so enforce descriptive ones separately.
      "@typescript-eslint/naming-convention": [
        "error",
        {
          selector: "typeParameter",
          format: ["PascalCase"],
          custom: { regex: "^.{2,}$", match: true },
        },
      ],
    },
  },
  {
    files: ["**/*.ts"],
    ignores: ["**/__tests__/**", "**/*.test.ts", "test-setup.ts", "**/*.d.ts"],
    plugins: { u4i: { rules: { "destructured-params": destructuredParams } } },
    rules: {
      // Legacy violators are grandfathered in the baseline; the rule flags
      // stale keys, so convert a baselined function when touching its signature.
      "u4i/destructured-params": [
        "error",
        {
          allowNames: ["on", "off", "emit"],
          baseline: destructuredParamsBaseline,
          // Resolve baseline keys against frontend/, wherever ESLint runs from.
          root: import.meta.dirname,
        },
      ],
    },
  },
  {
    files: ["**/lib/debug.ts"],
    rules: { "no-console": "off" },
  },
];
