import { defineConfig } from "vite";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import basicSsl from "@vitejs/plugin-basic-ssl";

const useSSL = process.env.ENABLE_SSL === "true";
// String form (not `new URL(".", import.meta.url)`): under vitest's happy-dom
// environment the global URL is happy-dom's, which fileURLToPath rejects.
const __dirname = dirname(fileURLToPath(import.meta.url));

// "mode" defined through CLI options passed to vite, i.e. pnpm run _dev_ adds development as mode
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
    // No `https` key: when ENABLE_SSL is on, basicSsl() fills server.https
    // itself (it only skips an explicit `false`); otherwise it stays HTTP.
    // U4I_VITE_HOST is this spoke's `vite-<slug>` alias, which the hub
    // Playwright browser uses. Read here (inside the factory), not at module
    // top level, so each config evaluation sees the current env.
    allowedHosts: [
      "vite",
      "localhost",
      "127.0.0.1",
      ...(process.env.U4I_VITE_HOST ? [process.env.U4I_VITE_HOST] : []),
    ],
    // No `hmr` host/port: the Vite client derives the HMR socket from the URL
    // it was loaded from — localhost:<U4I_VITE_PORT> for the host browser,
    // vite-<slug>:5173 for the hub Playwright browser. (If that socket fails,
    // Vite's client retries localhost:<server.port>, i.e. :5173.)
    watch: {
      usePolling: true,
      interval: 1000,
    },
    // The default allow list is only the root (./frontend). Assets referenced by
    // CSS url() in dependencies (e.g. font-awesome fonts) resolve to realpaths
    // under pnpm's virtual store (node_modules/.pnpm) beside this config, so
    // allow that dir too.
    // The whole .pnpm store is allowed deliberately: dev-server-only tradeoff (versioned .pnpm/<pkg>@<ver> paths make per-package allows brittle; server.* is unused by `vite build`).
    fs: {
      allow: [
        resolve(__dirname, "frontend"),
        resolve(__dirname, "node_modules/.pnpm"),
      ],
    },
  },

  // Build configuration
  build: {
    // Output to Flask's static folder
    outDir: "../backend/static/dist",
    emptyOutDir: true,
    manifest: true,
    copyPublicDir: true,

    rollupOptions: {
      input: {
        // DO NOT CHANGE THESE PATHS — entry points are .ts, Vite resolves at build time
        // Vite is running from the project root in the container, so 'frontend/' prefix is required.
        // Entry point for splash page (login/register)
        splash: resolve(__dirname, "frontend/splash.ts"),
        // Entry point for logged-in area
        main: resolve(__dirname, "frontend/main.ts"),
        // Entry point for contact page
        contact: resolve(__dirname, "frontend/contact.ts"),
        // Entry point for error pages
        error: resolve(__dirname, "frontend/error.ts"),
        // Entry point for static pages (privacy/terms)
        navbar: resolve(__dirname, "frontend/navbar.ts"),
        // Entry point for admin metrics dashboard
        adminMetrics: resolve(__dirname, "frontend/admin-metrics.ts"),
        // Entry point for the admin portal shell (health, users, audit log)
        admin: resolve(__dirname, "frontend/admin.ts"),
        // Entry point for the user settings page
        settings: resolve(__dirname, "frontend/settings.ts"),
      },
    },

    sourcemap: true,
  },
}));
