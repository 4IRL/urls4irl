import { defineConfig } from "vitest/config";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  test: {
    root: __dirname,
    environment: "happy-dom",
    globals: true,
    include: ["**/*.test.{js,ts}"],
    setupFiles: ["./test-setup.js"],
    coverage: {
      provider: "v8",
      include: [
        "home/**/*.{js,ts}",
        "splash/**/*.{js,ts}",
        "lib/**/*.{js,ts}",
        "store/**/*.{js,ts}",
        "logic/**/*.{js,ts}",
      ],
      exclude: ["**/*.test.{js,ts}", "test-setup.js", "vitest.config.js"],
    },
  },
});
