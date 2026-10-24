import { APP_CONFIG } from "../../../lib/config.js";
import { getState } from "../../../store/app-store.js";

// Leaf module: imports only the store and config, never scheme/ or
// panel-settings/ siblings, so it cannot introduce an import cycle.

export const HTTPS_SCHEME = "https";

/**
 * The scheme a new URL panel starts on: the active UTub's default when it is a
 * whitelisted scheme, else the app default. The whitelist guard is a defensive
 * backstop (the server already resets an invalid stored section).
 */
export function getEffectiveDefaultScheme(): string {
  const stored = getState().settings?.urls?.default_url_scheme;
  if (
    typeof stored === "string" &&
    stored !== "" &&
    APP_CONFIG.constants.URL_SCHEMES.includes(stored)
  ) {
    return stored;
  }
  return APP_CONFIG.constants.URL_DEFAULT_SCHEME;
}

/** True only for an explicit hide flag together with an effective `https` default. */
export function isSchemeSelectorHidden(): boolean {
  return (
    getState().settings?.urls?.hide_scheme_selector === true &&
    getEffectiveDefaultScheme() === HTTPS_SCHEME
  );
}
