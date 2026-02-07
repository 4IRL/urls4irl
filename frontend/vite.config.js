import { defineConfig } from "vite";
import { resolve } from "path";

// "mode" defined through CLI options passed to vite, i.e. npm run _dev_ adds development as mode
export default defineConfig(({ mode }) => ({
  // Root directory for your frontend source
  root: "./frontend",

  // Base public path (matches Flask's static URL path)
  base: mode === "development" ? "/" : "/static/dist/",

  // Development server config
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    cors: true,
    hmr: {
      host: "localhost",
    },
  },

  // Build configuration
  build: {
    // Output to Flask's static folder
    outDir: "../src/static/dist",
    emptyOutDir: true,
    manifest: true,

    rollupOptions: {
      input: {
        // Entry point for splash page (login/register)
        //splash: resolve(__dirname, 'frontend/splash.js'),
        // Entry point for logged-in area
        main: resolve(__dirname, "frontend/main.js"),
      },
    },

    sourcemap: true,
  },
}));
