import { defineConfig } from "vitest/config";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  server: {
    // Tests import Jinja templates from ../backend via `?raw`; the default
    // allow list is only the pnpm workspace root (./frontend).
    fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
  },
  test: {
    root: __dirname,
    environment: "happy-dom",
    globals: true,
    include: ["**/*.test.ts"],
    setupFiles: ["./test-setup.ts"],
    coverage: {
      provider: "v8",
      include: [
        "home/**/*.ts",
        "splash/**/*.ts",
        "lib/**/*.ts",
        "store/**/*.ts",
        "logic/**/*.ts",
        "settings/**/*.ts",
      ],
      exclude: ["**/*.test.ts", "test-setup.ts", "vitest.config.ts"],
    },
  },
});
