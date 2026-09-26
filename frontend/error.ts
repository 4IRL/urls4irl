import "./lib/security-check.js";
import { emit, initMetricsClient } from "./lib/metrics-client.js";
import { UI_EVENTS } from "./types/metrics-events.js";

// The error page is a standalone document with no jQuery or Bootstrap scripts,
// so this entry point must not depend on them (lib/globals.js reads
// window.jQuery, which is undefined here on a fresh load).
function initErrorPage(): void {
  initMetricsClient();

  // Refresh button handler - removes hash and reloads
  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      emit({ event: UI_EVENTS.UI_ERROR_PAGE_REFRESH });
      window.location.href = window.location.href.split("#")[0];
    });
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initErrorPage, { once: true });
} else {
  initErrorPage();
}
