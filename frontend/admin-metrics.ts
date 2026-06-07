import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/admin/metrics-dashboard.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarRouting } from "./lib/navbar-shared.js";
import { initMetricsClient } from "./lib/metrics-client.js";
import { initMetricsDashboard } from "./admin/metrics-dashboard.js";

registerJQueryPlugins();
setupCSRF();

$(document).ready(() => {
  initCookieBanner();
  initNavbarRouting();
  initMetricsClient();
  initMetricsDashboard();
});
