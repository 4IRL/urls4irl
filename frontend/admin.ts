import "bootstrap/dist/css/bootstrap.min.css";
import "./styles/base.css";
import "./styles/admin/admin-portal.css";
import "./lib/security-check.js";
import { $ } from "./lib/globals.js";
import { registerJQueryPlugins } from "./lib/jquery-plugins.js";
import { setupCSRF } from "./lib/csrf.js";
import { initCookieBanner } from "./lib/cookie-banner.js";
import { initNavbarBackdrop, initNavbarRouting } from "./lib/navbar-shared.js";
import { initAuditLog } from "./admin/audit-log.js";
import { initHealthMonitor } from "./admin/health-monitor.js";
import { initUserSearch } from "./admin/user-search.js";

registerJQueryPlugins();
setupCSRF();

$(document).ready(() => {
  initCookieBanner();
  initNavbarRouting();
  initNavbarBackdrop();
  initHealthMonitor();
  initUserSearch();
  initAuditLog();
});
