import type { UserConfig } from "vite";

import viteConfig from "../vite.config.js";

const BASE_ALLOWED_HOSTS = ["vite", "localhost", "127.0.0.1"];

const BASIC_SSL_PLUGIN_NAME = "vite:basic-ssl";

function resolveDevConfig(): UserConfig {
  return viteConfig({ mode: "development", command: "serve" });
}

function pluginNames(config: UserConfig): string[] {
  return (config.plugins ?? [])
    .flat()
    .filter(
      (plugin) => plugin && typeof plugin === "object" && "name" in plugin,
    )
    .map((plugin) => (plugin as { name: string }).name);
}

describe("vite.config dev server", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("allowedHosts includes U4I_VITE_HOST when set", () => {
    vi.stubEnv("U4I_VITE_HOST", "vite-wt-a");

    const resolved = resolveDevConfig();

    expect(resolved.server?.allowedHosts).toEqual([
      ...BASE_ALLOWED_HOSTS,
      "vite-wt-a",
    ]);
  });

  it("allowedHosts omits it when unset", () => {
    // Empty is falsy, so it behaves as unset and masks any inherited value.
    vi.stubEnv("U4I_VITE_HOST", "");

    const resolved = resolveDevConfig();

    expect(resolved.server?.allowedHosts).toEqual(BASE_ALLOWED_HOSTS);
  });

  it("plugins include basicSsl when ENABLE_SSL=true", () => {
    vi.stubEnv("ENABLE_SSL", "true");

    expect(pluginNames(resolveDevConfig())).toContain(BASIC_SSL_PLUGIN_NAME);
  });

  it.each(["false", ""])(
    "plugins omit basicSsl when ENABLE_SSL=%j",
    (enableSsl) => {
      vi.stubEnv("ENABLE_SSL", enableSsl);

      expect(pluginNames(resolveDevConfig())).not.toContain(
        BASIC_SSL_PLUGIN_NAME,
      );
    },
  );

  it.each(["vite-wt-a", ""])(
    "hmr pins no port (U4I_VITE_HOST=%j)",
    (viteHost) => {
      vi.stubEnv("U4I_VITE_HOST", viteHost);

      const hmr = resolveDevConfig().server?.hmr;

      expect(typeof hmr === "object" && "port" in hmr).toBe(false);
    },
  );
});
