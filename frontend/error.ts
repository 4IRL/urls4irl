import "./lib/security-check.js";
import { APP_CONFIG } from "./lib/config.js";
import { emit, initMetricsClient } from "./lib/metrics-client.js";
import { UI_EVENTS } from "./types/metrics-events.js";

// Where "Click to Refresh" should send the user. The backend marks the button
// `data-reload-safe="false"` when the page answered a full-page non-GET request
// (e.g. a form POST to /login): reloading that URL would GET a POST-only route
// and land on a 405, so go back to the same-origin page that submitted it, or
// to the app's home route when there is no usable referrer.
export function getRefreshDestination({
  isReloadSafe,
  currentHref,
  referrer,
  origin,
}: {
  isReloadSafe: boolean;
  currentHref: string;
  referrer: string;
  origin: string;
}): string {
  if (isReloadSafe) return currentHref.split("#")[0];
  if (referrer && isSameOrigin({ url: referrer, origin })) return referrer;
  return APP_CONFIG.routes.home;
}

function isSameOrigin({
  url,
  origin,
}: {
  url: string;
  origin: string;
}): boolean {
  try {
    return new URL(url).origin === origin;
  } catch {
    return false;
  }
}

// The error page is a standalone document with no jQuery or Bootstrap scripts,
// so this entry point must not depend on them (lib/globals.js reads
// window.jQuery, which is undefined here on a fresh load).
function initErrorPage(): void {
  initMetricsClient();

  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      emit({ event: UI_EVENTS.UI_ERROR_PAGE_REFRESH });
      window.location.href = getRefreshDestination({
        isReloadSafe: refreshBtn.dataset.reloadSafe !== "false",
        currentHref: window.location.href,
        referrer: document.referrer,
        origin: window.location.origin,
      });
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initErrorPage, { once: true });
} else {
  initErrorPage();
}
