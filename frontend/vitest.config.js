import { defineConfig } from "vitest/config";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  test: {
    root: __dirname,
    environment: "happy-dom",
    globals: true,
    include: ["**/*.test.js"],
    setupFiles: ["./test-setup.js"],
    coverage: {
      provider: "v8",
      include: ["home/**/*.js", "splash/**/*.js", "lib/**/*.js"],
      exclude: ["**/*.test.js", "test-setup.js", "vitest.config.js"],
    },
  },
});
