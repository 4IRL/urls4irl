import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { emit, initMetricsClient } from "./lib/metrics-client.js";
import { UI_EVENTS } from "./lib/metrics-events.js";

$(document).ready(() => {
  initMetricsClient();

  // Refresh button handler - removes hash and reloads
  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      emit(UI_EVENTS.UI_ERROR_PAGE_REFRESH);
      window.location.href = window.location.href.split("#")[0];
    });
  }
});
