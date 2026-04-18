import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

export default [
  {
    files: ["**/*.ts"],
    languageOptions: { parser: tsParser },
    plugins: { "@typescript-eslint": tsPlugin },
    rules: {
      ...tsPlugin.configs.recommended.rules,
    },
  },
  {
    // main.ts uses `import *` for side-effect bundling; the namespace
    // bindings are not referenced directly but must remain so Vite
    // includes those modules in the build output.
    files: ["**/main.ts"],
    rules: {
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
];
