import { defineConfig } from "vite";
import { resolve } from "path";
import basicSsl from "@vitejs/plugin-basic-ssl";

const useSSL = process.env.ENABLE_SSL === "true";

// "mode" defined through CLI options passed to vite, i.e. npm run _dev_ adds development as mode
export default defineConfig(({ mode }) => ({
  plugins: useSSL ? [basicSsl()] : [],
  // Root directory for your frontend source
  root: "./frontend",

  // Public directory for static assets (vendor bundles, etc.)
  publicDir: "./public",

  // Base public path (matches Flask's static URL path)
  base: mode === "development" ? "/" : "/static/dist/",

  // Development server config
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    cors: true,
    https: useSSL,
    allowedHosts: ["vite", "localhost", "127.0.0.1"],
    // HMR host is intentionally not set - Vite will infer from page URL
    // This allows HMR to work for both local dev (localhost) and Selenium tests (vite hostname)
    hmr: {
      port: 5173,
    },
    watch: {
      usePolling: true,
      interval: 1000,
    },
  },

  // Build configuration
  build: {
    // Output to Flask's static folder
    outDir: "../src/static/dist",
    emptyOutDir: true,
    manifest: true,
    copyPublicDir: true,

    rollupOptions: {
      input: {
        // DO NOT CHANGE THESE PATHS.
        // Vite is running from the project root in the container, so 'frontend/' prefix is required.
        // Entry point for splash page (login/register)
        splash: resolve(__dirname, "frontend/splash.js"),
        // Entry point for logged-in area
        main: resolve(__dirname, "frontend/main.js"),
        // Entry point for contact page
        contact: resolve(__dirname, "frontend/contact.js"),
        // Entry point for error pages
        error: resolve(__dirname, "frontend/error.js"),
        // Entry point for static pages (privacy/terms)
        navbar: resolve(__dirname, "frontend/navbar.js"),
      },
    },

    sourcemap: true,
  },
}));
